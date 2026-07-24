"""补全并增强诗境：完整作者生平 + 写作处境 / 诗意心境 / 为何而写。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from poetry_fetch import search_poem  # noqa: E402

POEM_FILE = ROOT / "poems_data" / "poem.txt"
STORIES_FILE = ROOT / "poems_data" / "stories.json"


def _clean_line(text: str) -> str:
    s = text.strip().strip("“”\"'")
    return re.sub(r"[。，、；！？…—\s]+$", "", s)


def load_poems_from_text() -> list[tuple[Optional[str], str]]:
    from poem_admin import load_poems_from_text as _load

    return _load()


def load_stories() -> dict[str, Any]:
    if not STORIES_FILE.exists():
        return {}
    return json.loads(STORIES_FILE.read_text(encoding="utf-8"))


def save_stories(stories: dict[str, Any]) -> None:
    STORIES_FILE.write_text(json.dumps(stories, ensure_ascii=False, indent=2), encoding="utf-8")


def is_truncated_background(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return True
    if t.endswith("…") or t.endswith("...") or t.endswith("⋯"):
        return True
    # 典型「作者（朝）传记截断」模式且偏短
    if re.match(r".+（.+）.+", t) and len(t) <= 200 and ("进士" in t or "字" in t):
        if "或为化用" in t:
            return False
        return True
    return False


def _pick_imagery_note(text: str) -> str:
    blob = text or ""
    rules = [
        (("雨", "听雨", "夜雨", "风雨"), "夜雨或风雨意象鲜明，像是独处时把心事交给天声。"),
        (("梦", "梦魂", "梦回"), "梦与醒交叠，常写追忆、空想或求而不得。"),
        (("酒", "醉", "杯"), "酒意贯穿其间，或放达，或借酒压住起伏心绪。"),
        (("月", "明月", "月光"), "以月为伴，多属望人、怀远或自照清夜。"),
        (("春", "花", "桃花", "落花"), "借春光花事，写韶光易逝或喜气初生。"),
        (("秋", "雁", "霜", "黄叶"), "秋气清冷，易落于羁旅、迟暮与家国之思。"),
        (("归", "乡", "家"), "归与未归之间，漂泊感最重。"),
        (("舟", "江", "水", "渡"), "行旅在水路之上，心随江流起伏。"),
        (("山", "云", "隐"), "山中云水，往往是退隐、自处或远离尘嚣的姿态。"),
        (("灯", "窗", "夜"), "窗灯夜坐，适合写静夜里细密的个人感受。"),
    ]
    hits = []
    for keys, note in rules:
        if any(k in blob for k in keys):
            hits.append(note)
        if len(hits) >= 2:
            break
    return "；".join(hits) if hits else "意象含蓄，重在气氛与余味，而非直白叙事。"


def _career_hint(bio: str) -> str:
    bio = bio or ""
    if any(k in bio for k in ("贬", "谪", "迁", "流放", "安置")):
        return "其生平屡经迁谪起伏，很多篇什写于仕途受挫、被迫安顿的阶段。"
    if any(k in bio for k in ("隐", "不仕", "遁", "归隐")):
        return "其人有退隐或不仕的选择，诗中常带出世后的清冷与自守。"
    if any(k in bio for k in ("战", "军", "塞", "兵")):
        return "生平与军旅边塞相关，部分作品写于行役、征途或家国动荡之中。"
    if any(k in bio for k in ("进士", "官", "知", "侍郎", "学士")):
        return "长期游走于仕途与地方任所之间，写作常夹杂公务余闲与迁转途中的见闻。"
    return "生平细节未必能精确钉死本诗写作年月，但作者的人生轨迹仍可帮助体会诗中处境。"


def build_story_from_meta(line: str, meta: dict[str, Any], existing: Optional[dict[str, Any]] = None) -> dict[str, str]:
    existing = existing if isinstance(existing, dict) else {}
    line_clean = _clean_line(line)
    author = meta.get("author_name") or ""
    dynasty = meta.get("dynasty_name") or ""
    title = meta.get("title") or ""
    source = meta.get("source") or existing.get("source") or "待考"
    full_poem = meta.get("full_poem") or existing.get("full_poem") or line
    bio = (meta.get("author_bio") or "").strip()
    api_bg = (meta.get("api_background") or "").strip()
    notes = meta.get("annotations") or []
    imagery = _pick_imagery_note(f"{line_clean}\n{full_poem}")
    career = _career_hint(bio)

    # 作者生平：完整不截断
    if bio:
        background = f"{author}（{dynasty}）{bio}" if author else bio
    elif not is_truncated_background(str(existing.get("background") or "")):
        background = str(existing.get("background") or "").strip()
    else:
        background = f"{author}（{dynasty}）生平资料暂缺，仅知本句出自{source}。" if author else f"本句出自{source}。"

    # 写作时的生活状态
    if api_bg:
        life_state = api_bg
    else:
        life_state = (
            f"《{title or '本篇'}》为{author or '作者'}所作。{career}"
            f"就名句「{line_clean}」看，{imagery}"
            f"写作时更像把眼前一事一景，收进当时真实的生活节奏里。"
        )

    # 诗中想表达的生活状态
    poem_mood = (
        f"这首诗想留住的，不只是字面风景，而是一种可反复进入的生活状态：{imagery}"
        f"读「{line_clean}」，更像看见作者如何安放自己的夜晚、旅途或心事。"
    )

    # 为何而写
    if api_bg:
        why_write = f"创作动机可参考本诗背景：{api_bg}"
    elif notes:
        why_write = (
            f"作者写下《{title or '此篇'}》，是为把某一刻经验凝成可传诵的句子。"
            f"旧注提示：{notes[0][:180]}"
        )
    else:
        why_write = (
            f"写《{title or '此篇'}》，多半不是为了说明一件事，而是为了保存一种心情："
            f"让后人读到「{line_clean}」时，仍能感到那一刻为何值得被记住。"
        )

    interpretation = str(existing.get("interpretation") or "").strip()
    if not interpretation or "可独立品读" in interpretation or "常单独摘出" in interpretation:
        interpretation = (
            f"名句「{line_clean}」出自{source}。"
            f"对照全诗《{title or '本篇'}》，可见它不是孤零零的金句，而是整篇气氛里最醒目的一笔。"
            f"{imagery}"
        )
        if notes:
            interpretation += f"\n\n注：{notes[0][:260]}"

    meaning = str(existing.get("meaning") or "").strip()
    if not meaning or "作为晚安诗" in meaning and len(meaning) < 60:
        meaning = (
            f"它适合被慢慢读完：不是催促结论，而是让你在字句里停一停，"
            f"体会{author or '作者'}当时想留住的那种生活余味。"
        )

    return {
        "source": source,
        "full_poem": full_poem,
        "background": background,
        "life_state": life_state,
        "poem_mood": poem_mood,
        "why_write": why_write,
        "interpretation": interpretation,
        "meaning": meaning,
    }


def enhance_without_meta(line: str, existing: dict[str, Any]) -> dict[str, str]:
    existing = dict(existing or {})
    line_clean = _clean_line(line)
    imagery = _pick_imagery_note(line_clean)
    background = str(existing.get("background") or "").strip()
    if is_truncated_background(background):
        background = f"「{line_clean}」暂未在公开诗库精确匹配到原作；以下按文本本身理解。"

    life_state = str(existing.get("life_state") or "").strip() or (
        f"具体写作时地难考。从句子本身看，{imagery}"
    )
    poem_mood = str(existing.get("poem_mood") or "").strip() or (
        f"它更接近一种可共享的生活状态：{imagery}"
    )
    why_write = str(existing.get("why_write") or "").strip() or (
        f"写下「{line_clean}」，是为把一瞬间的感受留住，让后来的人也能走进同一片心境。"
    )
    interpretation = str(existing.get("interpretation") or "").strip() or (
        f"此句「{line_clean}」可独立品读：{imagery}"
    )
    meaning = str(existing.get("meaning") or "").strip() or (
        "作为睡前一读，重在余味，不在考证。"
    )
    return {
        "source": str(existing.get("source") or "待考").strip() or "待考",
        "full_poem": str(existing.get("full_poem") or line).strip() or line,
        "background": background,
        "life_state": life_state,
        "poem_mood": poem_mood,
        "why_write": why_write,
        "interpretation": interpretation,
        "meaning": meaning,
    }


def needs_enrich(story: Any) -> bool:
    if not isinstance(story, dict):
        return True
    if is_truncated_background(str(story.get("background") or "")):
        return True
    for key in ("life_state", "poem_mood", "why_write"):
        if not str(story.get(key) or "").strip():
            return True
    return False


def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", errors="replace").decode("ascii", errors="replace"))


def main() -> int:
    parser = argparse.ArgumentParser(description="补全并增强诗境故事")
    parser.add_argument("--all", action="store_true", help="处理全部")
    parser.add_argument("--only-missing", action="store_true", help="仅补全截断/缺字段条目")
    parser.add_argument("--id", type=int, help="只处理指定 id")
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if not args.all and not args.only_missing and not args.id:
        parser.error("请指定 --all、--only-missing 或 --id")

    items = load_poems_from_text()
    stories = load_stories()
    targets: list[tuple[int, str]] = []
    for i, (_, content) in enumerate(items, start=1):
        if args.id and i != args.id:
            continue
        existing = stories.get(str(i))
        if args.id or args.all or needs_enrich(existing):
            targets.append((i, content))

    if args.limit > 0:
        targets = targets[: args.limit]

    _safe_print(f"todo {len(targets)} / {len(items)}")
    done = 0
    hit = 0
    for poem_id, content in targets:
        existing = stories.get(str(poem_id)) if isinstance(stories.get(str(poem_id)), dict) else {}
        _safe_print(f"[{poem_id}] {content[:28]}...")
        try:
            meta = search_poem(content)
            if meta:
                story = build_story_from_meta(content, meta, existing)
                if existing and not is_truncated_background(str(existing.get("background") or "")):
                    old_bg = str(existing.get("background") or "").strip()
                    if old_bg and len(old_bg) < 220 and "进士" not in old_bg[:40]:
                        if old_bg not in story["life_state"]:
                            story["life_state"] = old_bg + "\n\n" + story["life_state"]
                hit += 1
                status = f"hit score={meta.get('match_score')}"
            else:
                story = enhance_without_meta(content, existing or {})
                status = "miss"
            stories[str(poem_id)] = story
            save_stories(stories)
            done += 1
            _safe_print(f"  {status} saved")
        except Exception as exc:
            _safe_print(f"  fail: {type(exc).__name__}: {exc}")
        time.sleep(args.delay)

    from poem_admin import build_poems_json

    build_poems_json()
    _safe_print(f"done {done} hit {hit}, updated stories.json / poems.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
