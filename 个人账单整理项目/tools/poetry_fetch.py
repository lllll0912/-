"""古诗文开放检索：查名句出处、全诗与作者生平（不截断）。"""

from __future__ import annotations

import re
import time
from typing import Any, Optional

import requests

API_BASE = "https://www.sdtf.online/gushiwen-api"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "bill-poem-enrich/1.0"})


def _clean_line(text: str) -> str:
    s = text.strip().strip("“”\"'《》")
    s = re.sub(r"[。，、；！？…—\s]+$", "", s)
    return s


def _search_queries(line: str) -> list[str]:
    line = _clean_line(line)
    parts = [p.strip() for p in re.split(r"[，。；！？]", line) if len(p.strip()) >= 2]
    queries = [line, *parts]
    if len(line) > 8:
        queries.append(line[:8])
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _score_item(line: str, item: dict[str, Any], preview: str = "") -> int:
    line = _clean_line(line)
    score = 0
    preview = preview or item.get("content_preview") or item.get("summary") or ""
    if line in preview:
        score += 100
    for part in re.split(r"[，。；！？]", line):
        part = part.strip()
        if len(part) >= 2 and part in preview:
            score += 30
    if item.get("is_famous"):
        score += 5
    score += min(int(item.get("popularity") or 0), 20)
    return score


def _work_content(detail: dict[str, Any]) -> str:
    content = (detail.get("content") or detail.get("content_preview") or "").strip()
    if not content:
        paras = detail.get("paragraphs") or []
        chunks = []
        for p in paras:
            if isinstance(p, str):
                chunks.append(p)
            elif isinstance(p, dict):
                chunks.append(str(p.get("content") or p.get("text") or ""))
        content = "\n".join(x for x in chunks if x.strip())
    return re.sub(r"\n{3,}", "\n\n", content).strip()


def search_poem(line: str, timeout: int = 20) -> Optional[dict[str, Any]]:
    candidates: list[tuple[int, str, str]] = []

    for q in _search_queries(line):
        try:
            r = SESSION.get(f"{API_BASE}/search", params={"q": q}, timeout=timeout)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException:
            continue

        for item in data.get("items") or []:
            slug = item.get("slug")
            if not slug:
                continue
            preview = item.get("content_preview") or item.get("summary") or ""
            score = _score_item(line, item, preview)
            candidates.append((score, slug, preview))
        time.sleep(0.08)

    if not candidates:
        return None

    # 先按搜索预览分排序，再详查前几名
    candidates.sort(key=lambda x: x[0], reverse=True)
    seen_slug: set[str] = set()
    best_slug: Optional[str] = None
    best_score = -1
    for score, slug, preview in candidates:
        if slug in seen_slug:
            continue
        seen_slug.add(slug)
        try:
            detail = SESSION.get(f"{API_BASE}/works/{slug}", timeout=timeout).json()
        except requests.RequestException:
            continue
        full_preview = _work_content(detail) or preview
        score2 = _score_item(line, {"is_famous": False, "popularity": 0}, full_preview) + min(score, 40)
        if score2 > best_score:
            best_score = score2
            best_slug = slug
        if len(seen_slug) >= 5:
            break
        time.sleep(0.08)

    if not best_slug or best_score < 30:
        return None

    try:
        detail = SESSION.get(f"{API_BASE}/works/{best_slug}", timeout=timeout).json()
    except requests.RequestException:
        return None

    author = detail.get("author") or {}
    dynasty = detail.get("dynasty") or {}
    biography = ""
    author_slug = author.get("slug")
    if author_slug:
        try:
            ar = SESSION.get(f"{API_BASE}/authors/{author_slug}", timeout=timeout)
            ar.raise_for_status()
            author_detail = ar.json()
            biography = str(author_detail.get("biography") or "").strip()
        except requests.RequestException:
            pass

    content = _work_content(detail)
    ann = detail.get("annotations") or []
    notes = []
    for a in ann[:4]:
        if isinstance(a, dict):
            note = str(a.get("content") or a.get("text") or "").strip()
            if note:
                notes.append(note)

    return {
        "source": f"{dynasty.get('name', '')} · {author.get('name', '')}《{detail.get('title', '')}》".strip(" ·"),
        "full_poem": content,
        "author_bio": biography,
        "title": str(detail.get("title") or "").strip(),
        "author_name": str(author.get("name") or "").strip(),
        "dynasty_name": str(dynasty.get("name") or "").strip(),
        "api_background": str(detail.get("background") or detail.get("summary") or "").strip(),
        "annotations": notes,
        "match_score": best_score,
    }
