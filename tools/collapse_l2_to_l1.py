"""一次性：折叠二级类型到一级，并扁平化 category_rules.json。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "modules" / "bills"))
os.chdir(ROOT)

from rule_manager import RULE_FILE, _normalize_rules, save_rules  # noqa: E402
from db.schema import init_db  # noqa: E402
from db.repository import collapse_categories_to_single_level  # noqa: E402
from db.connector import get_cursor  # noqa: E402


def main() -> None:
    init_db()
    raw = json.loads(Path(RULE_FILE).read_text(encoding="utf-8"))
    rules, legacy = _normalize_rules(raw)
    # 若磁盘已扁平，尝试用旁路 legacy 文件
    legacy_path = ROOT / "data" / "_legacy_l2_map.json"
    if legacy_path.exists():
        file_legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        # 仅补充 k!=v 的映射
        for k, v in file_legacy.items():
            if k != v and k not in legacy:
                legacy[k] = v
            elif k != v:
                legacy[k] = v
    print("legacy diffs:")
    for k, v in sorted(legacy.items()):
        if k != v:
            print(f"  {k} -> {v}")
    n = collapse_categories_to_single_level(legacy)
    print("db touch count", n)
    save_rules(rules)
    marker = ROOT / "data" / ".category_single_level_v1"
    marker.write_text("ok\n", encoding="utf-8")
    print("rules flat consume keys:", list(rules["CONSUME_MAP"].keys()))
    with get_cursor() as cur:
        cur.execute(
            "SELECT category, category_l1, COUNT(*) AS c FROM records "
            "GROUP BY category, category_l1 ORDER BY c DESC LIMIT 20"
        )
        for r in cur.fetchall():
            print(dict(r))


if __name__ == "__main__":
    main()
