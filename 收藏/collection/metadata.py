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
_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)
_OG_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    re.I,
)
_DMM_IMG_RE = re.compile(
    r'https://pics\.dmm\.co\.jp/digital/video/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\.(?:jpg|jpeg|webp)',
    re.I,
)
_JAVDB_COVER_RE = re.compile(
    r'https://www\.javdatabase\.com/covers/full/[^"\'\s>]+\.(?:webp|jpg|jpeg|png)',
    re.I,
)
_MGSTAGE_FULL_RE = re.compile(
    r'data-image-src=["\'](https://image\.mgstage\.com/[^"\']+cap_e_\d+[^"\']+\.jpg)["\']',
    re.I,
)
_DMM_THUMB_SUFFIX = re.compile(r"p[st]\.jpe?g$", re.I)


def _is_thumb_url(url: str) -> bool:
    """过滤 javdatabase thumb、mgstage cap_t*、DMM ps/pt 等预览小图。"""
    u = (url or "").strip()
    if not u:
        return True
    low = u.lower()
    if "/covers/thumb/" in low or "/idolimages/thumb/" in low:
        return True
    if "cap_t" in low and "mgstage.com" in low:
        return True
    if "pics.dmm.co.jp" in low and _DMM_THUMB_SUFFIX.search(low):
        return True
    return False


def _url_dedupe_key(url: str) -> str:
    """同一帧/同一封面只保留一张（优先高清）。"""
    u = (url or "").strip()
    low = u.lower()
    m = re.search(r"cap_e_(\d+)", u, re.I)
    if m:
        return f"shot:{m.group(1)}"
    m = re.search(r"jp-(\d+)\.jpe?g", low)
    if m:
        return f"shot:{m.group(1)}"
    if "pl.jpe" in low or "/covers/full/" in low:
        return "cover"
    return u


def _filter_artwork_urls(urls: list[str], *, cover: str = "") -> list[str]:
    """去重并去掉缩略图；封面始终排第一。"""
    ordered: list[str] = []
    seen_keys: set[str] = set()
    if cover and not _is_thumb_url(cover):
        ordered.append(cover)
        seen_keys.add(_url_dedupe_key(cover))
    for u in urls:
        u = (u or "").strip()
        if not u or _is_thumb_url(u):
            continue
        key = _url_dedupe_key(u)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if u not in ordered:
            ordered.append(u)
    return ordered


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


_DISC_SUFFIX_RE = re.compile(r"^([A-Z]+)-(\d+)([A-Z])$")


def _disc_base_code(code: str) -> str:
    """NKKD-202C → NKKD-202（单字母碟后缀）。"""
    norm = normalize_movie_id(code)
    m = _DISC_SUFFIX_RE.match(norm)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return norm


def _slug_variants(code: str) -> list[str]:
    norm = normalize_movie_id(code)
    bases = [norm]
    base = _disc_base_code(norm)
    if base != norm:
        bases.append(base)

    out: list[str] = []
    for item in bases:
        m = re.match(r"^([A-Z]+)-(\d+)$", item)
        if not m:
            slug = item.lower()
            if slug not in out:
                out.append(slug)
            continue
        prefix, num = m.group(1), m.group(2)
        slugs = [f"{prefix.lower()}-{num}", f"{prefix.lower()}{num}"]
        if len(num) < 3:
            slugs.append(f"{prefix.lower()}-{num.zfill(3)}")
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


def _parse_image_urls(html: str) -> tuple[str, list[str]]:
    """从作品页提取封面 URL + 剧照/样图 URL 列表（仅高清，不含 thumb）。"""
    cover = ""
    for rx in (_OG_IMAGE_RE, _OG_IMAGE_RE2):
        m = rx.search(html or "")
        if m:
            u = m.group(1).strip()
            if not _is_thumb_url(u):
                cover = u
                break
    if not cover:
        covers = [u for u in _JAVDB_COVER_RE.findall(html or "") if not _is_thumb_url(u)]
        if covers:
            cover = covers[0]

    samples: list[str] = []
    seen: set[str] = set()

    # mgstage 高清剧照（data-image-src 指向 cap_e_*）
    for url in _MGSTAGE_FULL_RE.findall(html or ""):
        u = url.strip()
        if u in seen or _is_thumb_url(u):
            continue
        seen.add(u)
        samples.append(u)

    # DMM 样图：只要 jp-N，不要 pl/ps/pt（pl 作封面）
    for url in _DMM_IMG_RE.findall(html or ""):
        u = url.strip()
        if u in seen or _is_thumb_url(u):
            continue
        low = u.lower()
        if low.endswith("pl.jpg") or low.endswith("pl.jpeg"):
            if not cover:
                cover = u
            continue
        if "jp-" not in low:
            continue
        seen.add(u)
        samples.append(u)

    # 无 mgstage 剧照时，由 DMM pl 封面推导 jp-1..jp-12
    if not samples and cover:
        m = re.match(
            r"(https://pics\.dmm\.co\.jp/digital/video/[^/]+/[^/]+?)pl\.jpe?g$",
            cover,
            re.I,
        )
        if m:
            base = m.group(1)
            for i in range(1, 13):
                u = f"{base}jp-{i}.jpg"
                if u not in seen:
                    samples.append(u)
                    seen.add(u)

    return cover, _filter_artwork_urls(samples, cover=cover)


def _parse_movie_page(html: str, code: str) -> Optional[dict[str, Any]]:
    if not html or "404" in (re.findall(r"<h1[^>]*>([^<]+)", html, re.I)[:1] or [""])[0]:
        return None
    idols = _IDOL_RE.findall(html)
    if not idols:
        # 仍尝试只取图（少数页女优结构不同）
        cover, images = _parse_image_urls(html)
        h1 = (_H1_RE.findall(html) or [""])[0]
        title = _parse_title(h1, code)
        if not cover and not title:
            return None
        return {
            "person": "",
            "title": title,
            "cover_url": cover,
            "image_urls": images,
        }
    names: list[str] = []
    for _, name in idols:
        n = name.strip()
        if n and n not in names:
            names.append(n)
    h1 = (_H1_RE.findall(html) or [""])[0]
    cover, images = _parse_image_urls(html)
    return {
        "person": "、".join(names),
        "title": _parse_title(h1, code),
        "cover_url": cover,
        "image_urls": images,
    }


def _lookup_remote(code: str) -> Optional[dict[str, Any]]:
    for slug in _slug_variants(code):
        status, html = _fetch_html(f"https://www.javdatabase.com/movies/{slug}/")
        time.sleep(_FETCH_GAP_SEC)
        if status != 200:
            continue
        parsed = _parse_movie_page(html, code)
        if parsed and (parsed.get("person") or parsed.get("cover_url") or parsed.get("title")):
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
    """返回 {ok, id, person, title, cover_url, image_urls, source, error, cached}。"""
    mov_id = normalize_movie_id(code)
    if not mov_id:
        return {"ok": False, "id": "", "error": "invalid_code"}

    cache = _load_cache()
    key = _cache_key(mov_id)
    if use_cache and key in cache and _cache_fresh(cache[key]):
        hit = cache[key]
        if hit.get("error") == "not_found":
            # 碟后缀番号（如 NKKD-202C）可能对应母盘 NKKD-202，不因精确 slug 未命中而长期缓存拒绝
            if _disc_base_code(mov_id) == mov_id:
                return {"ok": False, "id": mov_id, "error": "not_found", "cached": True}
        return {
            "ok": True,
            "id": mov_id,
            "person": hit.get("person") or "",
            "title": hit.get("title") or "",
            "cover_url": hit.get("cover_url") or "",
            "image_urls": list(hit.get("image_urls") or []),
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
        "person": remote.get("person") or "",
        "title": remote.get("title") or "",
        "cover_url": remote.get("cover_url") or "",
        "image_urls": list(remote.get("image_urls") or [])[:20],
        "source": "javdatabase",
        "fetched_at": today,
    }
    _save_cache(cache)
    return {
        "ok": True,
        "id": mov_id,
        "person": remote.get("person") or "",
        "title": remote.get("title") or "",
        "cover_url": remote.get("cover_url") or "",
        "image_urls": list(remote.get("image_urls") or []),
        "source": "javdatabase",
        "cached": False,
    }


def download_image_bytes(url: str) -> Optional[bytes]:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Referer": "https://www.javdatabase.com/"},
            timeout=25,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        raw = resp.content or b""
        if len(raw) < 4000:
            return None
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "image" not in ctype and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return None
        return raw
    except requests.RequestException:
        return None


def fetch_movie_artwork(code: str, *, max_images: int = 10) -> dict[str, Any]:
    """查询并下载封面+剧照字节。返回 {ok, id, person, title, files:[(filename,bytes),...], error}。"""
    meta = lookup_movie_metadata(code, use_cache=True)
    mov_id = meta.get("id") or normalize_movie_id(code)
    # 旧缓存可能没有封面字段，强制刷新一次
    if meta.get("ok") and not (meta.get("cover_url") or meta.get("image_urls")):
        meta = lookup_movie_metadata(code, use_cache=False)
        mov_id = meta.get("id") or mov_id
    if not meta.get("ok"):
        return {
            "ok": False,
            "id": mov_id,
            "person": "",
            "title": "",
            "files": [],
            "error": meta.get("error") or "not_found",
        }

    urls = _filter_artwork_urls(list(meta.get("image_urls") or []), cover=(meta.get("cover_url") or ""))

    files: list[tuple[str, bytes]] = []
    seen_bytes_sig: set[tuple[int, int]] = set()
    for i, url in enumerate(urls[: max(1, max_images)]):
        raw = download_image_bytes(url)
        if not raw:
            continue
        # 同尺寸字节签名视为重复（常见于 thumb/full 漏网）
        sig = (len(raw), hash(raw[:512]) % (2**31))
        if sig in seen_bytes_sig:
            continue
        seen_bytes_sig.add(sig)
        ext = ".jpg"
        low = url.lower()
        if ".webp" in low:
            ext = ".webp"
        elif ".png" in low:
            ext = ".png"
        prefix = "cover" if i == 0 else f"sample_{i:02d}"
        files.append((f"{prefix}{ext}", raw))
        time.sleep(0.15)

    return {
        "ok": True,
        "id": mov_id,
        "person": meta.get("person") or "",
        "title": meta.get("title") or "",
        "files": files,
        "error": "" if files else "no_images",
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
