"""从 backup/records_backup_*.csv 恢复到本地 SQLite。"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db.schema import init_db  # noqa: E402
from db.connector import get_cursor  # noqa: E402


def restore_csv(csv_path: Path) -> int:
    init_db()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    with get_cursor(dictionary=False) as cur:
        cur.execute("DELETE FROM staging_records")
        cur.execute("DELETE FROM import_batches")
        cur.execute("DELETE FROM records")
        n = 0
        for row in rows:
            cur.execute(
                """
                INSERT INTO records (
                    id, bill_date, amount, detail, note, direction, category_l1, category,
                    is_travel, travel_tag, travel_companions, source_batch_id,
                    inserted_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["id"]) if row.get("id") else None,
                    row.get("bill_date") or "",
                    float(row.get("amount") or 0),
                    row.get("detail") or "",
                    row.get("note") or "",
                    row.get("direction") or "支出",
                    row.get("category_l1") or "",
                    row.get("category") or "其他消费",
                    int(row.get("is_travel") or 0),
                    row.get("travel_tag") or "",
                    row.get("travel_companions") or "",
                    int(row["source_batch_id"]) if row.get("source_batch_id") else None,
                    row.get("inserted_at") or None,
                    row.get("created_at") or None,
                    row.get("updated_at") or None,
                ),
            )
            n += 1
        # keep sqlite_sequence in sync for future inserts
        cur.execute("DELETE FROM sqlite_sequence WHERE name='records'")
        cur.execute("SELECT MAX(id) FROM records")
        mx = cur.fetchone()[0]
        if mx:
            cur.execute(
                "INSERT INTO sqlite_sequence(name, seq) VALUES('records', ?)",
                (mx,),
            )
    return n


def main():
    backup_dir = ROOT / "backup"
    csvs = sorted(backup_dir.glob("records_backup_*.csv"), reverse=True)
    # prefer full records dump (not _types/_travel)
    csvs = [p for p in csvs if "_types" not in p.name and "_travel" not in p.name]
    if not csvs:
        raise SystemExit("No records_backup_*.csv found in backup/")
    target = csvs[0]
    print("Restoring from", target)
    n = restore_csv(target)
    print("Restored", n, "records into data/bills.db")


if __name__ == "__main__":
    main()
