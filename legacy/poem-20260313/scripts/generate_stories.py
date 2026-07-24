"""批量生成 / 补全 stories.json — 新诗句自动查出处并写解读。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from build_poems_json import build, load_poems_from_text  # noqa: E402
from poetry_fetch import lookup_to_story_fields, search_poem  # noqa: E402
from story_llm import enrich_story_with_llm, llm_configured  # noqa: E402

STORIES_FILE = ROOT / "stories.json"


def load_stories() -> dict[str, Any]:
    if not STORIES_FILE.exists():
        return {}
    return json.loads(STORIES_FILE.read_text(encoding="utf-8"))


def save_stories(stories: dict[str, Any]) -> None:
    STORIES_FILE.write_text(json.dumps(stories, ensure_ascii=False, indent=2), encoding="utf-8")


def story_complete(story: Any) -> bool:
    if not isinstance(story, dict):
        return False
    required = ("source", "full_poem", "background", "interpretation", "meaning")
    return all(str(story.get(k) or "").strip() for k in required)


def generate_one(poem_id: int, content: str, use_llm: bool) -> dict[str, str]:
    meta = search_poem(content)
    if meta:
        draft = lookup_to_story_fields(content, meta)
    else:
        draft = {
            "source": "待考",
            "full_poem": content,
            "background": f"「{content}」或为化用、摘句或近现代语汇，暂未在公开诗库中精确匹配到原作。",
            "interpretation": f"此句「{content}」可独立品读：字句之间自有意境，不必强绑某一篇目。",
            "meaning": "作为晚安诗，重在今夜读之所得：让意象在睡前慢慢展开即可。",
        }

    if use_llm:
        draft = enrich_story_with_llm(content, draft, meta)
    return draft


def main() -> int:
    parser = argparse.ArgumentParser(description="自动生成诗句故事")
    parser.add_argument("--all", action="store_true", help="处理全部诗句")
    parser.add_argument("--only-missing", action="store_true", help="仅补全缺失/不完整的条目")
    parser.add_argument("--id", type=int, help="只处理指定 id")
    parser.add_argument("--no-llm", action="store_true", help="不用大模型，仅诗词库检索")
    parser.add_argument("--delay", type=float, default=0.35, help="每条间隔秒数")
    parser.add_argument("--limit", type=int, default=0, help="最多处理条数，0 为不限制")
    args = parser.parse_args()

    items = load_poems_from_text()
    stories = load_stories()
    use_llm = (not args.no_llm) and llm_configured()

    print(f"诗库 {len(items)} 条 | 大模型: {'开启' if use_llm else '关闭（仅 API 检索）'}")

    targets: list[tuple[int, str]] = []
    for i, (_, content) in enumerate(items, start=1):
        if args.id and i != args.id:
            continue
        existing = stories.get(str(i))
        if args.only_missing or args.all:
            if args.all or not story_complete(existing):
                targets.append((i, content))
        elif args.id:
            targets.append((i, content))

    if not targets and not args.id:
        if not args.only_missing and not args.all:
            parser.error("请指定 --all、--only-missing 或 --id")
        print("没有需要处理的条目。")
        return 0

    if args.limit > 0:
        targets = targets[: args.limit]

    done = 0
    for poem_id, content in targets:
        print(f"[{poem_id}/{len(items)}] {content[:24]}...")
        try:
            story = generate_one(poem_id, content, use_llm)
            stories[str(poem_id)] = story
            save_stories(stories)
            done += 1
        except Exception as exc:
            print(f"  失败: {exc}", file=sys.stderr)
        time.sleep(args.delay)

    print(f"完成 {done} 条，已写入 {STORIES_FILE}")
    build()
    print("已更新 site/poems.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
