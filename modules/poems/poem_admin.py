from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# modules/poems/poem_admin.py → 站点根
SITE_ROOT = Path(__file__).resolve().parents[2]
LEGACY_POEM_ROOT = SITE_ROOT / "legacy" / "poem-20260313"
POEM_FILE_NAME = "poem.txt"
STORIES_FILE_NAME = "stories.json"
OUT_FILE_NAME = "poems.json"


def _poem_root() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        root = Path(data_dir) / "poems"
    else:
        root = SITE_ROOT / "poems_data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _poem_file() -> Path:
    return _poem_root() / POEM_FILE_NAME


def _stories_file() -> Path:
    return _poem_root() / STORIES_FILE_NAME


def _out_file() -> Path:
    return _poem_root() / OUT_FILE_NAME


def ensure_poem_data() -> None:
    root = _poem_root()
    poem_file = _poem_file()
    stories_file = _stories_file()
    if poem_file.exists():
        return
    legacy_poem = LEGACY_POEM_ROOT / POEM_FILE_NAME
    legacy_stories = LEGACY_POEM_ROOT / STORIES_FILE_NAME
    bundled_poem = SITE_ROOT / "poems_data" / POEM_FILE_NAME
    bundled_stories = SITE_ROOT / "poems_data" / STORIES_FILE_NAME
    if legacy_poem.exists():
        shutil.copy2(legacy_poem, poem_file)
    elif bundled_poem.exists():
        shutil.copy2(bundled_poem, poem_file)
    if legacy_stories.exists():
        shutil.copy2(legacy_stories, stories_file)
    elif bundled_stories.exists():
        shutil.copy2(bundled_stories, stories_file)
    if poem_file.exists():
        build_poems_json()


def normalise_date(raw: str) -> Optional[datetime]:
    s = raw.strip()
    if not s:
        return None
    m = re.fullmatch(r"20210-(\d{2})-(\d{2})", s)
    if m:
        return datetime.strptime(f"2021-{m.group(1)}-{m.group(2)}", "%Y-%m-%d")
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        return datetime(int(y), int(mo), int(d))
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", s)
    if m:
        mo, d = m.groups()
        return datetime(2021, int(mo), int(d))
    return None


def extract_content(line: str) -> Optional[str]:
    s = line.strip()
    if not s:
        return None
    if "“" in s and "”" in s:
        start = s.find("“") + 1
        end = s.rfind("”")
        if start < end:
            return s[start:end].strip()
    if '"' in s:
        start = s.find('"') + 1
        end = s.rfind('"')
        if start < end:
            return s[start:end].strip()
    return s


def load_poems_from_text() -> list[tuple[Optional[str], str]]:
    ensure_poem_data()
    text = _poem_file().read_text(encoding="utf-8")
    lines = [ln.rstrip("\n") for ln in text.splitlines()]
    items: list[tuple[Optional[str], str]] = []
    current_date: Optional[str] = None
    started = False
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line == ".":
            current_date = None
            continue
        dt = normalise_date(line)
        if dt:
            current_date = dt.strftime("%Y-%m-%d")
            started = True
            continue
        if not started:
            continue
        if "号，我跟女朋友" in line or "好梦诗词" in line:
            continue
        content = extract_content(line)
        if not content:
            continue
        if any(k in content for k in ("同居", "朋友", "更新）")) and "。" in content:
            continue
        items.append((current_date or "", content))
    return items


def load_stories() -> dict[str, Any]:
    ensure_poem_data()
    path = _stories_file()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if v}


def _normalize_story(raw: Any) -> dict[str, str]:
    if isinstance(raw, dict):
        return {
            "source": str(raw.get("source") or "").strip(),
            "full_poem": str(raw.get("full_poem") or "").strip(),
            "background": str(raw.get("background") or "").strip(),
            "life_state": str(raw.get("life_state") or "").strip(),
            "poem_mood": str(raw.get("poem_mood") or "").strip(),
            "why_write": str(raw.get("why_write") or "").strip(),
            "interpretation": str(raw.get("interpretation") or "").strip(),
            "meaning": str(raw.get("meaning") or "").strip(),
        }
    if isinstance(raw, str) and raw.strip():
        return {"interpretation": raw.strip()}
    return {
        "source": "",
        "full_poem": "",
        "background": "",
        "life_state": "",
        "poem_mood": "",
        "why_write": "",
        "interpretation": "",
        "meaning": "",
    }


def story_has_content(story: dict[str, str]) -> bool:
    return any(
        str(story.get(k) or "").strip()
        for k in (
            "source",
            "full_poem",
            "background",
            "life_state",
            "poem_mood",
            "why_write",
            "interpretation",
            "meaning",
        )
    )


def _poem_date_sort_key(poem: dict[str, Any]) -> tuple[float, int]:
    raw = str(poem.get("poem_date") or "").strip()
    if not raw:
        return (-1.0, int(poem.get("id", 0)))
    try:
        ts = datetime.strptime(raw, "%Y-%m-%d").timestamp()
    except ValueError:
        ts = -1.0
    return (ts, int(poem.get("id", 0)))


def sort_poems_desc(poems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 poem_date 降序；同日再按 id 降序；无日期排最后。"""
    return sorted(poems, key=_poem_date_sort_key, reverse=True)


def build_poems_json() -> list[dict[str, Any]]:
    items = load_poems_from_text()
    stories = load_stories()
    poems: list[dict[str, Any]] = []
    for idx, (poem_date, content) in enumerate(items, start=1):
        raw = stories.get(str(idx)) or stories.get(content)
        story = _normalize_story(raw) if raw else {}
        poems.append(
            {
                "id": idx,
                "poem_date": poem_date,
                "content": content,
                "story": story if story_has_content(story) else None,
            }
        )
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(poems),
        "poems": poems,
    }
    _out_file().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return poems


def load_poems() -> list[dict[str, Any]]:
    ensure_poem_data()
    built = build_poems_json()
    poems: list[dict[str, Any]] = []
    for item in built:
        story = item.get("story") or {}
        poems.append(
            {
                "id": int(item["id"]),
                "poem_date": str(item.get("poem_date") or "").strip(),
                "content": str(item.get("content") or "").strip(),
                "story": _normalize_story(story),
            }
        )
    return sort_poems_desc(poems)


def get_poem(poem_id: int) -> Optional[dict[str, Any]]:
    for poem in load_poems():
        if int(poem.get("id", 0)) == poem_id:
            return poem
    return None


def _date_hash(date_str: str) -> int:
    h = 2166136261
    for ch in date_str:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def pick_poem_for_date(date_str: str, poems: Optional[list[dict[str, Any]]] = None) -> Optional[dict[str, Any]]:
    items = poems if poems is not None else load_poems()
    if not items:
        return None
    idx = _date_hash(date_str) % len(items)
    return items[idx]


def _read_poem_intro() -> str:
    ensure_poem_data()
    text = _poem_file().read_text(encoding="utf-8")
    lines = text.splitlines()
    intro: list[str] = []
    started = False
    date_pattern = re.compile(r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}|20210-\d{2}-\d{2})$")
    for raw in lines:
        line = raw.strip()
        if date_pattern.fullmatch(line):
            started = True
            break
        intro.append(raw.rstrip("\n"))
    if started:
        return "\n".join(intro).rstrip() + "\n\n"
    return text.rstrip() + ("\n\n" if text.strip() else "")


def save_poems(poems: list[dict[str, Any]]) -> None:
    ensure_poem_data()
    cleaned: list[dict[str, Any]] = []
    for item in poems:
        story = _normalize_story(item.get("story") or {})
        cleaned.append(
            {
                "poem_date": str(item.get("poem_date") or "").strip(),
                "content": str(item.get("content") or "").strip(),
                "story": story,
            }
        )
    cleaned = [x for x in cleaned if x["poem_date"] and x["content"]]
    cleaned.sort(key=lambda x: (x["poem_date"], x["content"]))

    intro = _read_poem_intro()
    poem_blocks: list[str] = [intro.rstrip()] if intro.strip() else []
    for item in cleaned:
        poem_blocks.extend([item["poem_date"], "", f"“{item['content']}”", ""])
    _poem_file().write_text("\n".join(poem_blocks).rstrip() + "\n", encoding="utf-8")

    stories_payload: dict[str, Any] = {}
    for idx, item in enumerate(cleaned, start=1):
        if story_has_content(item["story"]):
            stories_payload[str(idx)] = item["story"]
    _stories_file().write_text(json.dumps(stories_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    build_poems_json()


def upsert_poem(poem_id: Optional[int], payload: dict[str, Any]) -> int:
    poems = load_poems()
    story = _normalize_story(payload.get("story") or {})
    normalized = {
        "poem_date": str(payload.get("poem_date") or "").strip(),
        "content": str(payload.get("content") or "").strip(),
        "story": story,
    }
    if poem_id is None:
        poems.append(normalized)
    else:
        updated = False
        for item in poems:
            if int(item.get("id", 0)) == poem_id:
                item.update(normalized)
                updated = True
                break
        if not updated:
            raise ValueError("诗词不存在")
    save_poems(poems)
    for item in load_poems():
        if item["poem_date"] == normalized["poem_date"] and item["content"] == normalized["content"]:
            return int(item["id"])
    return int(poem_id or 0)


def delete_poem(poem_id: int) -> bool:
    poems = load_poems()
    kept = [item for item in poems if int(item.get("id", 0)) != poem_id]
    if len(kept) == len(poems):
        return False
    save_poems(kept)
    return True
