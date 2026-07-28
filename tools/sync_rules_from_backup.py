"""
从本机 backup/（或指定目录）里最新的 records_backup_*_types.json
恢复类型字典到 data/category_rules.json，便于「按线上数据本地开发」。

用法（在项目根）:
  .\\.venv\\Scripts\\python.exe tools\\sync_rules_from_backup.py
  .\\.venv\\Scripts\\python.exe tools\\sync_rules_from_backup.py --dir backup
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "modules" / "bills"))

from rule_manager import ensure_rules_file, get_rules_path, save_rules  # noqa: E402


def _find_latest_types(backup_dir: Path) -> Path | None:
    if not backup_dir.is_dir():
        return None
    cands = sorted(
        backup_dir.glob("records_backup_*_types.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return cands[0] if cands else None


def _to_rules(payload: dict) -> dict:
    # 备份里可能是完整 rules，或带 travel 的包；也兼容只有 MAP 的结构
    if "CONSUME_MAP" in payload or "INCOME_MAP" in payload:
        return {
            "CONSUME_MAP": payload.get("CONSUME_MAP") or {},
            "INCOME_MAP": payload.get("INCOME_MAP") or {},
        }
    raise ValueError("不是有效的类型字典 JSON（缺少 CONSUME_MAP / INCOME_MAP）")


def main() -> int:
    ap = argparse.ArgumentParser(description="从备份恢复类型字典到本地 data/")
    ap.add_argument(
        "--dir",
        default=str(ROOT / "backup"),
        help="备份目录（默认项目 backup/）",
    )
    ap.add_argument("--file", default="", help="直接指定 *_types.json 路径")
    args = ap.parse_args()

    src: Path | None
    if args.file:
        src = Path(args.file)
    else:
        src = _find_latest_types(Path(args.dir))

    if not src or not src.is_file():
        print("[ERROR] 未找到 records_backup_*_types.json，请先在正式站导出/同步备份到 backup/")
        return 1

    payload = json.loads(src.read_text(encoding="utf-8"))
    rules = _to_rules(payload)
    ensure_rules_file()
    save_rules(rules)
    dest = get_rules_path()
    print("[OK] 已从 {} 恢复类型字典 -> {}".format(src, dest))
    print(
        "    支出 {} 条，收入 {} 条".format(
            len(rules.get("CONSUME_MAP") or {}),
            len(rules.get("INCOME_MAP") or {}),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
