"""诗库维护：按现有风格推荐名句、手动查诗并生成诗境预览。"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

from poetry_fetch import SESSION, API_BASE, search_poem, _clean_line, _work_content
from enrich_poem_stories import build_story_from_meta, enhance_without_meta

IMAGERY_TAGS = (
    ("雨", "听雨", "夜雨", "风雨"),
    ("梦", "梦魂", "梦回"),
    ("月", "明月", "月光"),
    ("春", "花", "桃花", "落花"),
    ("秋", "雁", "霜", "黄叶"),
    ("酒", "醉", "杯"),
    ("归", "乡", "家"),
    ("江", "水", "舟", "渡"),
    ("山", "云", "隐"),
    ("灯", "窗", "夜"),
    ("相思", "愁", "泪"),
    ("风", "雪", "寒"),
)


def existing_contents(poems: list[dict[str, Any]]) -> set[str]:
    return {_clean_line(str(p.get("content") or "")) for p in poems if str(p.get("content") or "").strip()}


def style_profile(poems: list[dict[str, Any]]) -> dict[str, Any]:
    tag_counter: Counter[str] = Counter()
    dynasty_counter: Counter[str] = Counter()
    samples: list[str] = []
    for poem in poems:
        content = str(poem.get("content") or "")
        if content and len(samples) < 12:
            samples.append(content)
        blob = content + " " + json.dumps(poem.get("story") or {}, ensure_ascii=False)
        for group in IMAGERY_TAGS:
            if any(k in blob for k in group):
                tag_counter[group[0]] += 1
        source = str((poem.get("story") or {}).get("source") or "")
        m = re.match(r"([^·\s]+)", source)
        if m:
            dynasty_counter[m.group(1)] += 1
    top_tags = [t for t, _ in tag_counter.most_common(6)] or ["月", "雨", "春", "梦", "秋"]
    top_dynasties = [d for d, _ in dynasty_counter.most_common(3)]
    return {
        "top_tags": top_tags,
        "top_dynasties": top_dynasties,
        "samples": samples,
        "count": len(poems),
    }


def _pick_couple_from_text(text: str) -> str:
    """从全诗正文抽出较像「名句」的一两句。"""
    text = (text or "").strip().replace("\r", "")
    if not text:
        return ""
    sentences = re.split(r"[。！？\n]+", text)
    sentences = [s.strip("，、； 　") for s in sentences if s.strip()]
    candidates: list[str] = []
    for sent in sentences:
        clauses = [c.strip() for c in re.split(r"[，、；]", sent) if c.strip()]
        if len(clauses) >= 2:
            couple = f"{clauses[0]}，{clauses[1]}"
            if 8 <= len(couple) <= 36:
                candidates.append(couple)
            elif 5 <= len(clauses[0]) <= 18:
                candidates.append(clauses[0])
        elif 5 <= len(sent) <= 24:
            candidates.append(sent)
    if candidates:
        # 偏好长度适中的联句
        candidates.sort(key=lambda s: abs(len(s) - 16))
        return candidates[0]
    return _clean_line(text)[:28]


_CLASSICAL_DYNASTIES = ("先秦", "汉", "魏晋", "南北朝", "隋", "唐", "五代", "宋", "金", "元", "明", "清")


def _is_classical_source(source: str) -> bool:
    s = source or ""
    if any(x in s for x in ("近现代", "当代", "民国")):
        return False
    return any(d in s for d in _CLASSICAL_DYNASTIES)


def _prefer_seeds(tags: list[str]) -> list[str]:
    """单字意象扩成更易搜到名句的短语。"""
    expand = {
        "雨": ["夜雨", "听雨", "春雨"],
        "梦": ["梦回", "梦魂", "春梦"],
        "月": ["明月", "月明", "清月"],
        "春": ["春风", "春江", "桃花"],
        "秋": ["秋风", "秋思", "黄叶"],
        "酒": ["对酒", "醉", "把酒"],
        "归": ["归去", "思归", "故乡"],
        "江": ["江水", "渡江", "江头"],
        "山": ["空山", "青山", "山中"],
        "灯": ["夜灯", "残灯", "灯火"],
        "相思": ["相思", "相思树"],
        "风": ["长风", "西风", "秋风"],
        "雪": ["风雪", "雪夜"],
        "寒": ["岁寒", "寒夜"],
    }
    out: list[str] = []
    for t in tags:
        out.extend(expand.get(t, [t]))
    # 兜底常见意象，避免库里标签偏怪时搜不到
    out.extend(["明月", "夜雨", "春风", "落花", "孤灯"])
    seen: set[str] = set()
    uniq: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq[:12]


def _search_seed_candidates(seed: str, existing: set[str], limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        r = SESSION.get(f"{API_BASE}/search", params={"q": seed}, timeout=15)
        r.raise_for_status()
        items = (r.json() or {}).get("items") or []
    except requests.RequestException:
        return out

    for item in items[:12]:
        dynasty_hint = item.get("dynasty_name") or ""
        if dynasty_hint and not _is_classical_source(dynasty_hint):
            continue
        slug = item.get("slug")
        if not slug:
            continue
        try:
            detail = SESSION.get(f"{API_BASE}/works/{slug}", timeout=12).json()
        except requests.RequestException:
            continue
        preview = _work_content(detail) or item.get("content_preview") or item.get("summary") or ""
        line = _clean_line(_pick_couple_from_text(preview))
        if not line or line in existing:
            continue
        if any(x["content"] == line for x in out):
            continue
        if len(line) < 5 or len(line) > 40:
            continue
        author = item.get("author_name") or (detail.get("author") or {}).get("name") or ""
        dynasty = dynasty_hint or (detail.get("dynasty") or {}).get("name") or ""
        title = item.get("title") or detail.get("title") or ""
        source = f"{dynasty} · {author}《{title}》".strip(" ·")
        if not _is_classical_source(source):
            continue
        meta = {
            "source": source,
            "full_poem": preview,
            "author_bio": "",
            "title": str(title).strip(),
            "author_name": str(author).strip(),
            "dynasty_name": str(dynasty).strip(),
            "api_background": str(detail.get("background") or detail.get("summary") or "").strip(),
            "annotations": [],
            "match_score": 70,
        }
        out.append(
            {
                "content": line,
                "reason": f"与诗库偏好意象「{seed}」相近",
                "source_hint": source,
                "slug": slug,
                "seed": seed,
                "meta": meta,
            }
        )
        if len(out) >= limit:
            break
    return out


def _llm_recommend_lines(profile: dict[str, Any], existing: set[str]) -> list[dict[str, str]]:
    try:
        from story_llm import llm_configured, _client_config, _chat_completions_url, extract_json_from_text
    except Exception:
        return []
    if not llm_configured():
        return []

    api_key, base_url, model = _client_config()
    prompt = {
        "style_tags": profile.get("top_tags") or [],
        "dynasties": profile.get("top_dynasties") or [],
        "samples": profile.get("samples") or [],
        "avoid": list(existing)[:40],
    }
    system = (
        "你是古典诗词荐书人。根据用户诗库风格，推荐5句真实存在的唐、宋、元、明、清名句。"
        "必须是文学史上确有的句子，禁止编造，禁止近现代作品。输出 JSON："
        '{"items":[{"content":"名句（一句或一联，不超过30字）","reason":"为何契合该诗库风格（20-40字）"}]}'
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        "temperature": 0.7,
    }
    try:
        r = requests.post(
            _chat_completions_url(base_url),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        r.raise_for_status()
        data = extract_json_from_text(r.json()["choices"][0]["message"]["content"])
        items = data.get("items") or []
        out = []
        for it in items:
            content = _clean_line(str(it.get("content") or ""))
            if not content or content in existing:
                continue
            out.append(
                {
                    "content": content,
                    "reason": str(it.get("reason") or "契合你现有诗库的气质").strip(),
                }
            )
        return out[:8]
    except Exception:
        return []


def _pack_from_meta(line: str, meta: Optional[dict[str, Any]], reason: str = "", use_llm: bool = False) -> dict[str, Any]:
    if meta:
        story = build_story_from_meta(line, meta, None)
        verified = True
        match_score = int(meta.get("match_score") or 70)
        source = story.get("source") or meta.get("source") or ""
    else:
        story = enhance_without_meta(line, {})
        verified = False
        match_score = 0
        source = story.get("source") or "待考"

    if use_llm:
        try:
            from story_llm import enrich_story_with_llm, llm_configured

            if llm_configured():
                story = enrich_story_with_llm(line, story, meta)
        except Exception:
            pass

    return {
        "content": line,
        "reason": reason,
        "verified": verified,
        "match_score": match_score,
        "source": source,
        "story": story,
        "meta": {
            "title": (meta or {}).get("title") or "",
            "author_name": (meta or {}).get("author_name") or "",
            "dynasty_name": (meta or {}).get("dynasty_name") or "",
        },
    }


def _compose_candidate_story(line: str, use_llm: bool = True) -> dict[str, Any]:
    meta = search_poem(line)
    packed = _pack_from_meta(line, meta, use_llm=use_llm)
    return packed


def recommend_poems(poems: list[dict[str, Any]], count: int = 5, use_llm: bool = True) -> list[dict[str, Any]]:
    """按现有诗库风格推荐若干可加入的名句（含诗境预览）。"""
    existing = existing_contents(poems)
    profile = style_profile(poems)
    packed_all: list[dict[str, Any]] = []
    seen: set[str] = set()

    # 1) 先按意象从公开诗库快速凑满（通常几秒内）
    for seed in _prefer_seeds(profile.get("top_tags") or [])[:5]:
        if len(packed_all) >= count:
            break
        for c in _search_seed_candidates(seed, existing | seen, limit=2):
            line = c["content"]
            if line in seen or line in existing:
                continue
            packed = _pack_from_meta(line, c.get("meta"), reason=c.get("reason") or "", use_llm=False)
            seen.add(line)
            packed_all.append(packed)
            if len(packed_all) >= count:
                break

    # 2) 不足时再用 LLM 补句并核实
    if use_llm and len(packed_all) < count:
        for item in _llm_recommend_lines(profile, existing | seen):
            c = _clean_line(item["content"])
            if not c or c in seen or c in existing or len(c) > 40:
                continue
            meta = search_poem(c)
            if not meta:
                continue
            source = str(meta.get("source") or "")
            if not _is_classical_source(source):
                continue
            packed = _pack_from_meta(c, meta, reason=item.get("reason") or "", use_llm=False)
            seen.add(c)
            packed_all.append(packed)
            if len(packed_all) >= count:
                break

    packed_all.sort(
        key=lambda x: (
            0 if x.get("verified") else 1,
            0 if _is_classical_source(str(x.get("source") or "")) else 1,
            -int(x.get("match_score") or 0),
        )
    )
    return packed_all[:count]


def lookup_poem_line(line: str, use_llm: bool = True) -> dict[str, Any]:
    line = _clean_line(line)
    if not line:
        return {"ok": False, "error": "请输入一句诗词"}
    packed = _compose_candidate_story(line, use_llm=use_llm)
    packed["ok"] = True
    packed["error"] = ""
    if packed["verified"]:
        packed["authenticity"] = "已在公开诗库匹配到出处"
    else:
        packed["authenticity"] = "暂未精确匹配到公开诗库原作，诗境为推断整理，请自行判断"
    return packed


def default_poem_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# --- 服务端缓存：避免把完整诗境塞进 cookie session ---

_CACHE_DIR = Path(__file__).resolve().parent.parent / "poems_data" / "intake_cache"


def _ensure_cache_dir() -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def _new_cache_id(prefix: str) -> str:
    import uuid

    return f"{prefix}_{uuid.uuid4().hex}"


def save_intake_batch(items: list[dict[str, Any]], key: Optional[str] = None) -> str:
    _ensure_cache_dir()
    key = key or _new_cache_id("batch")
    path = _CACHE_DIR / f"{key}.json"
    slim = []
    for it in items:
        slim.append(
            {
                "content": it.get("content") or "",
                "reason": it.get("reason") or "",
                "verified": bool(it.get("verified")),
                "match_score": int(it.get("match_score") or 0),
                "source": it.get("source") or "",
                "authenticity": it.get("authenticity") or "",
                "story": it.get("story") or {},
            }
        )
    path.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
    return key


def load_intake_batch(key: str) -> list[dict[str, Any]]:
    if not key:
        return []
    path = _CACHE_DIR / f"{key}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_intake_item(item: dict[str, Any]) -> str:
    _ensure_cache_dir()
    key = _new_cache_id("item")
    path = _CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
    return key


def load_intake_item(key: Optional[str]) -> Optional[dict[str, Any]]:
    if not key:
        return None
    path = _CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def clear_intake_item(key: Optional[str]) -> None:
    if not key:
        return
    path = _CACHE_DIR / f"{key}.json"
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
