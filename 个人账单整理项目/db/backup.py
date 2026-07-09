import csv
import json
import os
from datetime import datetime
from typing import List, Dict, Any

from db.connector import get_cursor
from rule_manager import load_rules


BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backup")
BACKUP_PREFIX = "records_backup_"


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
                   GROUP_CONCAT(DISTINCT NULLIF(travel_companions,'') ORDER BY travel_companions SEPARATOR '、') AS travel_companions,
                   MIN(bill_date) AS start_date,
                   MAX(bill_date) AS end_date,
                   DATEDIFF(MAX(bill_date), MIN(bill_date)) + 1 AS duration_days,
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


def write_latest_backup_csv() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for name in os.listdir(BACKUP_DIR):
        if name.startswith(BACKUP_PREFIX) and (name.endswith(".csv") or name.endswith(".txt") or name.endswith(".json")):
            try:
                os.remove(os.path.join(BACKUP_DIR, name))
            except Exception:
                pass

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, "{}{}.csv".format(BACKUP_PREFIX, ts))
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

    # 同步输出 CSV，便于人工查阅
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
            fieldnames=["travel_tag", "travel_companions", "start_date", "end_date", "duration_days", "record_count", "expense", "income"],
        )
        w.writeheader()
        for row in _query_travel_profiles():
            w.writerow(row)
    return backup_file
