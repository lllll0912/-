import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.connector import get_cursor


def to_jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    return value


def row_to_jsonable(row):
    return {k: to_jsonable(v) for k, v in row.items()}


def main():
    with get_cursor() as cur:
        cur.execute("SHOW TABLES")
        all_tables = cur.fetchall()

        cur.execute("DESC poems")
        schema_rows = cur.fetchall()

        cur.execute(
            """
            SELECT
              COUNT(*) AS total_poems,
              MIN(poem_date) AS earliest_date,
              MAX(poem_date) AS latest_date,
              SUM(done = 1) AS pushed_count,
              SUM(done = 0) AS not_pushed_count
            FROM poems
            """
        )
        stats = cur.fetchone()

        cur.execute(
            """
            SELECT id, poem_date, content, done, done_date, created_at
            FROM poems
            ORDER BY poem_date, id
            LIMIT 10
            """
        )
        sample = cur.fetchall()

        cur.execute(
            """
            SELECT id, poem_date, content, done, done_date
            FROM poems
            WHERE content LIKE %s
            LIMIT 5
            """,
            ("%竹斋眠听雨，梦里长青苔%",),
        )
        key_rows = cur.fetchall()

        cur.execute("SELECT COUNT(*) AS favorite_count FROM poem_favorites")
        favorite_stats = cur.fetchone()

    print("=== 当前数据库表 ===")
    print(json.dumps([row_to_jsonable(r) for r in all_tables], ensure_ascii=False, indent=2))
    print("=== poems 表结构 ===")
    print(json.dumps([row_to_jsonable(r) for r in schema_rows], ensure_ascii=False, indent=2))
    print("\n=== poems 统计信息 ===")
    print(json.dumps(row_to_jsonable(stats), ensure_ascii=False, indent=2))
    print("\n=== poems 前10条样例 ===")
    print(json.dumps([row_to_jsonable(r) for r in sample], ensure_ascii=False, indent=2))
    print("\n=== 关键诗句检查（竹斋眠听雨） ===")
    print(json.dumps([row_to_jsonable(r) for r in key_rows], ensure_ascii=False, indent=2))
    print("\n=== 收藏表统计 ===")
    print(json.dumps(row_to_jsonable(favorite_stats), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

