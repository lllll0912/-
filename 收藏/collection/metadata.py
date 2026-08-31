"""按番号从 javdatabase.com 查询女优与标题（带本地缓存）。"""

from __future__ import annotations

import json
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import requests

from .store import meta_root, normalize_movie_id

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_FETCH_GAP_SEC = 0.35
_NOT_FOUND_RETRY_DAYS = 7
_IDOL_RE = re.compile(
    r'href="https://www\.javdatabase\.com/idols/([^/]+)/"[^>]*>([^<]+)<',
    re.I,
)
_H1_RE = re.compile(r"<h1[^>]*>([^<]+)", re.I)
_MOVIE_LINK_RE = re.compile(
    r'href="(https://www\.javdatabase\.com/movies/([^"/]+)/)"',
    re.I,
)


def lookup_cache_path() -> Path:
    return meta_root() / "lookup_cache.json"


def _load_cache() -> dict[str, Any]:
    path = lookup_cache_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    path = lookup_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _cache_key(code: str) -> str:
    return normalize_movie_id(code)


def _slug_variants(code: str) -> list[str]:
    norm = normalize_movie_id(code)
    m = re.match(r"^([A-Z]+)-(\d+)$", norm)
    if not m:
        return [norm.lower()]
    prefix, num = m.group(1), m.group(2)
    slugs = [f"{prefix.lower()}-{num}", f"{prefix.lower()}{num}"]
    if len(num) < 3:
        slugs.append(f"{prefix.lower()}-{num.zfill(3)}")
    out: list[str] = []
    for s in slugs:
        if s not in out:
            out.append(s)
    return out


def _parse_title(h1: str, code: str) -> str:
    s = (h1 or "").strip()
    if not s or s.lower() == "404":
        return ""
    m = re.match(r"^[A-Z0-9-]+\s*-\s*(.+)$", s, re.I)
    if m:
        return m.group(1).strip()
    prefix = normalize_movie_id(code)
    if s.upper().startswith(prefix):
        return s[len(prefix) :].lstrip(" -").strip()
    return s


def _fetch_html(url: str) -> tuple[int, str]:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "en,ja;q=0.8"},
            timeout=18,
            allow_redirects=True,
        )
        return resp.status_code, resp.text or ""
    except requests.RequestException:
        return 0, ""


def _parse_movie_page(html: str, code: str) -> Optional[dict[str, str]]:
    if not html or "404" in (re.findall(r"<h1[^>]*>([^<]+)", html, re.I)[:1] or [""])[0]:
        return None
    idols = _IDOL_RE.findall(html)
    if not idols:
        return None
    names: list[str] = []
    for _, name in idols:
        n = name.strip()
        if n and n not in names:
            names.append(n)
    h1 = (_H1_RE.findall(html) or [""])[0]
    return {
        "person": "、".join(names),
        "title": _parse_title(h1, code),
    }


def _lookup_remote(code: str) -> Optional[dict[str, str]]:
    for slug in _slug_variants(code):
        status, html = _fetch_html(f"https://www.javdatabase.com/movies/{slug}/")
        time.sleep(_FETCH_GAP_SEC)
        if status != 200:
            continue
        parsed = _parse_movie_page(html, code)
        if parsed:
            return parsed

    norm = normalize_movie_id(code)
    status, html = _fetch_html(f"https://www.javdatabase.com/?s={quote(norm)}")
    time.sleep(_FETCH_GAP_SEC)
    if status != 200:
        return None
    links = _MOVIE_LINK_RE.findall(html)
    for _, slug in links:
        if slug.lower() not in _slug_variants(code):
            continue
        status2, html2 = _fetch_html(f"https://www.javdatabase.com/movies/{slug}/")
        time.sleep(_FETCH_GAP_SEC)
        if status2 != 200:
            continue
        parsed = _parse_movie_page(html2, code)
        if parsed:
            return parsed
    return None


def _cache_fresh(entry: dict[str, Any]) -> bool:
    raw = (entry.get("fetched_at") or "")[:10]
    if not raw:
        return False
    try:
        fetched = date.fromisoformat(raw)
    except ValueError:
        return False
    if entry.get("error") == "not_found":
        return fetched >= date.today() - timedelta(days=_NOT_FOUND_RETRY_DAYS)
    return True


def lookup_movie_metadata(code: str, *, use_cache: bool = True) -> dict[str, Any]:
    """返回 {ok, id, person, title, source, error, cached}。"""
    mov_id = normalize_movie_id(code)
    if not mov_id:
        return {"ok": False, "id": "", "error": "invalid_code"}

    cache = _load_cache()
    key = _cache_key(mov_id)
    if use_cache and key in cache and _cache_fresh(cache[key]):
        hit = cache[key]
        if hit.get("error") == "not_found":
            return {"ok": False, "id": mov_id, "error": "not_found", "cached": True}
        return {
            "ok": True,
            "id": mov_id,
            "person": hit.get("person") or "",
            "title": hit.get("title") or "",
            "source": hit.get("source") or "cache",
            "cached": True,
        }

    remote = _lookup_remote(mov_id)
    today = date.today().isoformat()
    if not remote:
        cache[key] = {"error": "not_found", "fetched_at": today}
        _save_cache(cache)
        return {"ok": False, "id": mov_id, "error": "not_found", "cached": False}

    cache[key] = {
        "person": remote["person"],
        "title": remote["title"],
        "source": "javdatabase",
        "fetched_at": today,
    }
    _save_cache(cache)
    return {
        "ok": True,
        "id": mov_id,
        "person": remote["person"],
        "title": remote["title"],
        "source": "javdatabase",
        "cached": False,
    }


def apply_metadata_to_movie(row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """仅在字段为空时写入查询结果。"""
    out = dict(row)
    if meta.get("ok"):
        if not (out.get("person") or "").strip() and meta.get("person"):
            out["person"] = meta["person"]
        if not (out.get("title") or "").strip() and meta.get("title"):
            out["title"] = meta["title"]
    return out


def backfill_missing_metadata(*, max_fetch: int = 10) -> dict[str, int]:
    """为 catalog 中缺女优名的作品批量补全（受 max_fetch 限制）。"""
    from .store import enrich_movie, load_catalog, save_catalog

    catalog = load_catalog()
    movies = list(catalog.get("movies") or [])
    fetched = updated = skipped = 0

    for i, raw in enumerate(movies):
        if fetched >= max_fetch:
            break
        m = enrich_movie(raw)
        if (m.get("person") or "").strip():
            skipped += 1
            continue
        mid = (m.get("id") or "").strip()
        if not mid:
            continue
        meta = lookup_movie_metadata(mid)
        fetched += 1
        if not meta.get("ok"):
            continue
        nm = apply_metadata_to_movie(movies[i], meta)
        if nm != movies[i]:
            movies[i] = {
                **movies[i],
                "person": nm.get("person") or "",
                "title": nm.get("title") or movies[i].get("title") or "",
            }
            updated += 1

    if updated:
        catalog["movies"] = movies
        save_catalog(catalog)
    return {"fetched": fetched, "updated": updated, "skipped": skipped}
