import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple

from db.connector import get_cursor
from rule_manager import load_rules


BACKUP_PREFIX = "records_backup_"


def get_backup_dir() -> str:
    """本机用项目下 backup/；Fly 用 Volume 上 /data/backup（持久）。"""
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return str(Path(data_dir) / "backup")
    # modules/bills/db → 站点根 /backup
    return str(Path(__file__).resolve().parents[3] / "backup")


BACKUP_DIR = get_backup_dir()  # 兼容旧引用；运行时请用 get_backup_dir()


def _query_all_records() -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, bill_date, amount, detail, note, direction, category_l1, category,
                   is_travel, travel_tag, travel_companions, source_batch_id, inserted_at, created_at, updated_at
            FROM records
            ORDER BY bill_date DESC, id DESC
            """
        )
        return cur.fetchall()


def _query_travel_profiles() -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(NULLIF(travel_tag,''),'未命名行程') AS travel_tag,
                   GROUP_CONCAT(CASE WHEN travel_companions='' THEN NULL ELSE travel_companions END, '、') AS travel_companions,
                   MIN(bill_date) AS start_date,
                   MAX(bill_date) AS end_date,
                   CAST(julianday(MAX(bill_date)) - julianday(MIN(bill_date)) AS INTEGER) + 1 AS duration_days,
                   COUNT(*) AS record_count,
                   ROUND(SUM(CASE WHEN direction='支出' THEN amount ELSE 0 END), 2) AS expense,
                   ROUND(SUM(CASE WHEN direction='收入' THEN amount ELSE 0 END), 2) AS income
            FROM records
            WHERE is_travel=1
            GROUP BY COALESCE(NULLIF(travel_tag,''),'未命名行程')
            ORDER BY start_date, travel_tag
            """
        )
        return cur.fetchall()


def write_latest_backup_csv(clear_old: bool = True) -> str:
    """
    按现有命名写入 backup/：
      records_backup_YYYYMMDD_HHMMSS.csv / .txt
      records_backup_..._types.json/.csv
      records_backup_..._travel.json/.csv
    返回主 csv 路径。
    """
    backup_dir = get_backup_dir()
    os.makedirs(backup_dir, exist_ok=True)
    if clear_old:
        for name in os.listdir(backup_dir):
            if name.startswith(BACKUP_PREFIX) and (
                name.endswith(".csv") or name.endswith(".txt") or name.endswith(".json")
            ):
                try:
                    os.remove(os.path.join(backup_dir, name))
                except Exception:
                    pass

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, "{}{}.csv".format(BACKUP_PREFIX, ts))
    rows = _query_all_records()
    headers = [
        "id",
        "bill_date",
        "amount",
        "detail",
        "note",
        "direction",
        "category_l1",
        "category",
        "is_travel",
        "travel_tag",
        "travel_companions",
        "source_batch_id",
        "inserted_at",
        "created_at",
        "updated_at",
    ]
    with open(backup_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    txt_file = backup_file[:-4] + ".txt"
    with open(txt_file, "w", encoding="utf-8") as tf:
        for row in rows:
            tf.write(
                "{} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {}\n".format(
                    row.get("bill_date", ""),
                    row.get("detail", ""),
                    row.get("amount", ""),
                    row.get("direction", ""),
                    row.get("category_l1", ""),
                    row.get("category", ""),
                    row.get("is_travel", ""),
                    row.get("travel_tag", ""),
                    row.get("travel_companions", ""),
                    row.get("inserted_at", ""),
                    row.get("id", ""),
                )
            )

    base_no_ext = backup_file[:-4]
    types_file = base_no_ext + "_types.json"
    travel_file = base_no_ext + "_travel.json"
    with open(types_file, "w", encoding="utf-8") as f:
        json.dump(load_rules(), f, ensure_ascii=False, indent=2)
    with open(travel_file, "w", encoding="utf-8") as f:
        json.dump({"travel_profiles": _query_travel_profiles()}, f, ensure_ascii=False, indent=2, default=str)

    types_csv = base_no_ext + "_types.csv"
    with open(types_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["map", "category_l1", "category_l2", "pattern"])
        w.writeheader()
        rules = load_rules()
        for map_name in ("CONSUME_MAP", "INCOME_MAP"):
            grouped = rules.get(map_name, {}) or {}
            for l1, subs in grouped.items():
                for l2, pattern in (subs or {}).items():
                    w.writerow(
                        {
                            "map": map_name,
                            "category_l1": l1,
                            "category_l2": l2,
                            "pattern": pattern or "",
                        }
                    )

    travel_csv = base_no_ext + "_travel.csv"
    with open(travel_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "travel_tag",
                "travel_companions",
                "start_date",
                "end_date",
                "duration_days",
                "record_count",
                "expense",
                "income",
            ],
        )
        w.writeheader()
        for row in _query_travel_profiles():
            w.writerow(row)
    return backup_file


def list_backup_bundle_files(main_csv_path: str) -> List[str]:
    """同一时间戳的一套备份文件。"""
    base = main_csv_path[:-4]
    candidates = [
        main_csv_path,
        base + ".txt",
        base + "_types.json",
        base + "_types.csv",
        base + "_travel.json",
        base + "_travel.csv",
    ]
    return [p for p in candidates if os.path.isfile(p)]


def create_backup_bundle(clear_old: bool = True) -> Tuple[str, List[str]]:
    main_csv = write_latest_backup_csv(clear_old=clear_old)
    files = list_backup_bundle_files(main_csv)
    return main_csv, files
