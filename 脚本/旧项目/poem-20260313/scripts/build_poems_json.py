"""从 poem.txt 生成 site/poems.json，供静态站使用。"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
POEM_FILE = ROOT_DIR / "poem.txt"
STORIES_FILE = ROOT_DIR / "stories.json"
OUT_FILE = ROOT_DIR / "site" / "poems.json"


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


def load_poems_from_text() -> List[Tuple[Optional[str], str]]:
    text = POEM_FILE.read_text(encoding="utf-8")
    lines = [ln.rstrip("\n") for ln in text.splitlines()]

    items: List[Tuple[Optional[str], str]] = []
    current_date: Optional[str] = None
    started = False

    for raw in lines:
        line = raw.strip()
        if not line or line == ".":
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

        items.append((current_date, content))

    return items


def load_stories() -> dict[str, Any]:
    """stories.json：键为 id 或诗句全文，值为结构化故事对象或旧版字符串。"""
    if not STORIES_FILE.exists():
        return {}
    data = json.loads(STORIES_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if v}


def normalize_story(raw: Any) -> dict[str, str]:
    if isinstance(raw, dict):
        return {
            "source": str(raw.get("source") or "").strip(),
            "full_poem": str(raw.get("full_poem") or "").strip(),
            "background": str(raw.get("background") or "").strip(),
            "interpretation": str(raw.get("interpretation") or "").strip(),
            "meaning": str(raw.get("meaning") or "").strip(),
        }
    if isinstance(raw, str) and raw.strip():
        return {"interpretation": raw.strip()}
    return {}


def story_has_content(story: dict[str, str]) -> bool:
    return any(story.get(k) for k in ("source", "full_poem", "background", "interpretation", "meaning"))


def build() -> list[dict[str, Any]]:
    items = load_poems_from_text()
    stories = load_stories()
    poems: list[dict[str, Any]] = []

    for i, (poem_date, content) in enumerate(items, start=1):
        raw = stories.get(str(i)) or stories.get(content)
        story = normalize_story(raw) if raw else {}
        poems.append(
            {
                "id": i,
                "poem_date": poem_date,
                "content": content,
                "story": story if story_has_content(story) else None,
            }
        )

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(poems),
        "poems": poems,
    }
    OUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return poems


def main() -> int:
    if not POEM_FILE.exists():
        print(f"找不到 {POEM_FILE}", file=sys.stderr)
        return 1
    poems = build()
    print(f"已生成 {OUT_FILE}，共 {len(poems)} 条诗句。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
