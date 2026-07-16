"""从古诗文开放检索 API 查询名句出处与全诗。"""

from __future__ import annotations

import re
import time
from typing import Any, Optional
from urllib.parse import quote

import requests

API_BASE = "https://www.sdtf.online/gushiwen-api"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "daily-poem-bot/1.0"})


def _clean_line(text: str) -> str:
    s = text.strip().strip("“”\"'《》")
    s = re.sub(r"[。，、；！？…—\s]+$", "", s)
    return s


def _search_queries(line: str) -> list[str]:
    line = _clean_line(line)
    parts = re.split(r"[，。；！？]", line)
    parts = [p.strip() for p in parts if len(p.strip()) >= 2]
    queries = [line]
    queries.extend(parts)
    if len(line) > 8:
        queries.append(line[:8])
    # 去重保序
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


def search_poem(line: str, timeout: int = 20) -> Optional[dict[str, Any]]:
    """搜索并返回最佳匹配的作品详情。"""
    best_slug: Optional[str] = None
    best_score = -1
    best_preview = ""

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
            try:
                dr = SESSION.get(f"{API_BASE}/works/{slug}", timeout=timeout)
                dr.raise_for_status()
                detail = dr.json()
            except requests.RequestException:
                continue
            preview = detail.get("content") or detail.get("content_preview") or ""
            score = _score_item(line, item, preview)
            if score > best_score:
                best_score = score
                best_slug = slug
                best_preview = preview
        time.sleep(0.15)

    if not best_slug or best_score < 30:
        return None

    try:
        dr = SESSION.get(f"{API_BASE}/works/{best_slug}", timeout=timeout)
        dr.raise_for_status()
        detail = dr.json()
    except requests.RequestException:
        return None

    author = detail.get("author") or {}
    dynasty = detail.get("dynasty") or {}
    author_slug = author.get("slug")
    biography = ""
    if author_slug:
        try:
            ar = SESSION.get(f"{API_BASE}/authors/{author_slug}", timeout=timeout)
            ar.raise_for_status()
            bio = ar.json().get("biography") or ""
            biography = bio[:400]
        except requests.RequestException:
            pass

    content = (detail.get("content") or detail.get("content_preview") or "").strip()
    content = re.sub(r"\n{3,}", "\n\n", content)

    return {
        "source": f"{dynasty.get('name', '')} · {author.get('name', '')}《{detail.get('title', '')}》".strip(),
        "full_poem": content,
        "author_bio": biography,
        "title": detail.get("title", ""),
        "author_name": author.get("name", ""),
        "dynasty_name": dynasty.get("name", ""),
        "api_background": (detail.get("background") or "").strip(),
        "annotations": detail.get("annotations") or [],
        "match_score": best_score,
    }


def lookup_to_story_fields(line: str, meta: dict[str, Any]) -> dict[str, str]:
    """将检索结果转为故事字段（无大模型时的基础版）。"""
    source = meta["source"]
    full_poem = meta["full_poem"]
    line_clean = _clean_line(line)

    background = meta.get("api_background") or ""
    if not background and meta.get("author_bio"):
        background = (
            f"{meta['author_name']}（{meta['dynasty_name']}）"
            f"{meta['author_bio'][:180]}…"
            if len(meta["author_bio"]) > 180
            else f"{meta['author_name']}（{meta['dynasty_name']}）{meta['author_bio']}"
        )

    interpretation = (
        f"所选名句「{line_clean}」出自{source}。"
        f"全诗以「{meta.get('title', '')}」为篇名，上下文可对照原文细读。"
        f"此句常单独摘出，用以写夜雨、梦境或心境之幽微。"
    )

    meaning = (
        f"在{meta.get('dynasty_name', '古代')}诗歌语境中，"
        f"这类诗句多借景物写情，含蓄深远。"
        f"作为每日一诗，宜在静夜慢读，体会字句间的余韵。"
    )

    ann = meta.get("annotations") or []
    if ann:
        note = ann[0].get("content") or ann[0].get("text") or ""
        if note:
            interpretation = f"{interpretation}\n\n注：{note[:300]}"

    return {
        "source": source,
        "full_poem": full_poem,
        "background": background,
        "interpretation": interpretation,
        "meaning": meaning,
    }
