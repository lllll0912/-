from typing import Dict, List, Any, Optional

from db.connector import get_cursor


def create_import_batch(source_name: str, source_year: int, raw_text: str) -> int:
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            """
            INSERT INTO import_batches (source_name, source_year, raw_text, status)
            VALUES (%s, %s, %s, 'draft')
            """,
            (source_name, source_year, raw_text),
        )
        return cur.lastrowid


def get_batch(batch_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM import_batches WHERE id=%s", (batch_id,))
        return cur.fetchone()


def list_batches(limit: int = 20) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM import_batches ORDER BY id DESC LIMIT %s", (limit,))
        return cur.fetchall()


def insert_staging_records(batch_id: int, records: List[Dict[str, Any]]) -> None:
    if not records:
        return
    with get_cursor(dictionary=False) as cur:
        sql = """
        INSERT INTO staging_records (
            batch_id, row_index, bill_date, amount, detail, note, direction,
            category_l1, category, is_travel, travel_tag, is_valid, error_msg
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = []
        for r in records:
            values.append(
                (
                    batch_id,
                    int(r.get("row_index", 0)),
                    r.get("bill_date"),
                    float(r.get("amount", 0.0)),
                    str(r.get("detail", ""))[:255],
                    str(r.get("note", "")),
                    str(r.get("direction", "支出"))[:10],
                    str(r.get("category_l1", ""))[:50],
                    str(r.get("category", "其他消费"))[:50],
                    1 if r.get("is_travel") else 0,
                    str(r.get("travel_tag", ""))[:100],
                    1 if r.get("is_valid", True) else 0,
                    str(r.get("error_msg", ""))[:255],
                )
            )
        cur.executemany(sql, values)


def list_staging_records(batch_id: int) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM staging_records WHERE batch_id=%s ORDER BY row_index ASC, id ASC",
            (batch_id,),
        )
        return cur.fetchall()


def update_staging_record(record_id: int, payload: Dict[str, Any]) -> None:
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            """
            UPDATE staging_records
            SET bill_date=%s, amount=%s, detail=%s, note=%s, direction=%s,
                category_l1=%s, category=%s, is_travel=%s, travel_tag=%s, is_valid=%s, error_msg=%s
            WHERE id=%s
            """,
            (
                payload.get("bill_date"),
                float(payload.get("amount", 0.0)),
                str(payload.get("detail", ""))[:255],
                str(payload.get("note", "")),
                str(payload.get("direction", "支出"))[:10],
                str(payload.get("category_l1", ""))[:50],
                str(payload.get("category", "其他消费"))[:50],
                1 if payload.get("is_travel") else 0,
                str(payload.get("travel_tag", ""))[:100],
                1 if payload.get("is_valid", True) else 0,
                str(payload.get("error_msg", ""))[:255],
                record_id,
            ),
        )


def delete_staging_record(record_id: int) -> None:
    with get_cursor(dictionary=False) as cur:
        cur.execute("DELETE FROM staging_records WHERE id=%s", (record_id,))


def delete_staging_by_ids(batch_id: int, ids: List[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join(["%s"] * len(ids))
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            "DELETE FROM staging_records WHERE batch_id=%s AND id IN ({})".format(placeholders),
            tuple([batch_id] + ids),
        )
        return cur.rowcount


def delete_staging_by_date(batch_id: int, bill_date: str) -> int:
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            "DELETE FROM staging_records WHERE batch_id=%s AND bill_date=%s",
            (batch_id, bill_date),
        )
        return cur.rowcount


def confirm_batch(batch_id: int, replace_existing: bool = True) -> Dict[str, int]:
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            """
            SELECT DISTINCT bill_date
            FROM staging_records
            WHERE batch_id=%s AND is_valid=1 AND bill_date IS NOT NULL
            """,
            (batch_id,),
        )
        dates = [row[0] for row in cur.fetchall()]
        # 记录本次覆盖日期在“正式库”中的旅游打标快照（按日期）
        old_travel_map: Dict[str, Dict[str, str]] = {}
        if dates:
            placeholders = ",".join(["%s"] * len(dates))
            cur.execute(
                """
                SELECT bill_date,
                       COALESCE(NULLIF(travel_tag,''), '未命名行程') AS travel_tag,
                       COALESCE(travel_companions, '') AS travel_companions
                FROM records
                WHERE is_travel=1 AND bill_date IN ({})
                ORDER BY id DESC
                """.format(placeholders),
                tuple(dates),
            )
            for row in cur.fetchall():
                d = str(row[0]) if row and row[0] is not None else ""
                t = str(row[1]) if row and row[1] is not None else ""
                c = str(row[2]) if row and row[2] is not None else ""
                if d and d not in old_travel_map:
                    old_travel_map[d] = {"tag": t, "companions": c}

        deleted = 0
        if replace_existing and dates:
            placeholders = ",".join(["%s"] * len(dates))
            cur.execute("DELETE FROM records WHERE bill_date IN ({})".format(placeholders), tuple(dates))
            deleted = cur.rowcount

        cur.execute(
            """
            INSERT INTO records (
                bill_date, amount, detail, note, direction,
                category_l1, category, is_travel, travel_tag, travel_companions, source_batch_id, inserted_at
            )
            SELECT bill_date, amount, detail, note, direction,
                   category_l1, category, 0, '', '', batch_id, NOW()
            FROM staging_records
            WHERE batch_id=%s AND is_valid=1 AND bill_date IS NOT NULL
            """,
            (batch_id,),
        )
        inserted = cur.rowcount

        # 重新应用历史旅游打标（导入页不生效旅游字段，以旅游管理页面按日期维护为准）
        reapplied = 0
        for d, snap in old_travel_map.items():
            cur.execute(
                """
                UPDATE records
                SET is_travel=1, travel_tag=%s, travel_companions=%s
                WHERE source_batch_id=%s AND bill_date=%s
                """,
                (snap.get("tag", ""), snap.get("companions", ""), batch_id, d),
            )
            reapplied += cur.rowcount

        cur.execute(
            "UPDATE import_batches SET status='confirmed', confirmed_at=NOW() WHERE id=%s",
            (batch_id,),
        )
        return {"inserted": inserted, "replaced_deleted": deleted, "travel_reapplied": reapplied}


def list_records(filters: Dict[str, Any], limit: Optional[int] = 20) -> List[Dict[str, Any]]:
    where = []
    args: List[Any] = []

    if filters.get("year"):
        where.append("YEAR(bill_date)=%s")
        args.append(int(filters["year"]))
    if filters.get("month"):
        where.append("DATE_FORMAT(bill_date, '%Y-%m')=%s")
        args.append(filters["month"])
    if filters.get("direction"):
        where.append("direction=%s")
        args.append(filters["direction"])
    if filters.get("category_l1"):
        where.append("category_l1=%s")
        args.append(filters["category_l1"])
    if filters.get("category"):
        where.append("category=%s")
        args.append(filters["category"])
    if filters.get("is_travel") in ("0", "1"):
        where.append("is_travel=%s")
        args.append(int(filters["is_travel"]))
    if filters.get("keyword"):
        where.append("(detail LIKE %s OR note LIKE %s)")
        kw = f"%{filters['keyword']}%"
        args.extend([kw, kw])
    if filters.get("dates"):
        ds = [str(d).strip() for d in (filters.get("dates") or []) if str(d).strip()]
        if ds:
            placeholders = ",".join(["%s"] * len(ds))
            where.append("bill_date IN ({})".format(placeholders))
            args.extend(ds)

    sort_map = {
        "id": "id",
        "bill_date": "bill_date",
        "amount": "amount",
        "direction": "direction",
        "category_l1": "category_l1",
        "category": "category",
        "detail": "detail",
        "is_travel": "is_travel",
        "travel_tag": "travel_tag",
        "inserted_at": "inserted_at",
    }
    sort_by = sort_map.get(str(filters.get("sort_by", "")), "bill_date")
    sort_order = "ASC" if str(filters.get("sort_order", "")).lower() == "asc" else "DESC"

    sql = "SELECT * FROM records"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY {} {}, id DESC".format(sort_by, sort_order)
    if limit is not None:
        sql += " LIMIT %s"
        args.append(int(limit))

    with get_cursor() as cur:
        cur.execute(sql, tuple(args))
        return cur.fetchall()


def get_record(record_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM records WHERE id=%s", (record_id,))
        return cur.fetchone()


def create_record(payload: Dict[str, Any]) -> int:
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            """
            INSERT INTO records (
                bill_date, amount, detail, note, direction,
                category_l1, category, is_travel, travel_tag, travel_companions, inserted_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                payload["bill_date"],
                float(payload["amount"]),
                str(payload.get("detail", ""))[:255],
                str(payload.get("note", "")),
                str(payload.get("direction", "支出"))[:10],
                str(payload.get("category_l1", ""))[:50],
                str(payload.get("category", "其他消费"))[:50],
                1 if payload.get("is_travel") else 0,
                str(payload.get("travel_tag", ""))[:100],
                str(payload.get("travel_companions", ""))[:255],
            ),
        )
        return cur.lastrowid


def update_record(record_id: int, payload: Dict[str, Any]) -> None:
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            """
            UPDATE records
            SET bill_date=%s, amount=%s, detail=%s, note=%s, direction=%s,
                category_l1=%s, category=%s, is_travel=%s, travel_tag=%s, travel_companions=COALESCE(%s, travel_companions)
            WHERE id=%s
            """,
            (
                payload["bill_date"],
                float(payload["amount"]),
                str(payload.get("detail", ""))[:255],
                str(payload.get("note", "")),
                str(payload.get("direction", "支出"))[:10],
                str(payload.get("category_l1", ""))[:50],
                str(payload.get("category", "其他消费"))[:50],
                1 if payload.get("is_travel") else 0,
                str(payload.get("travel_tag", ""))[:100],
                (None if "travel_companions" not in payload else str(payload.get("travel_companions", ""))[:255]),
                record_id,
            ),
        )


def delete_record(record_id: int) -> None:
    with get_cursor(dictionary=False) as cur:
        cur.execute("DELETE FROM records WHERE id=%s", (record_id,))


def delete_records_by_ids(ids: List[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join(["%s"] * len(ids))
    with get_cursor(dictionary=False) as cur:
        cur.execute("DELETE FROM records WHERE id IN ({})".format(placeholders), tuple(ids))
        return cur.rowcount


def delete_records_by_date(bill_date: str) -> int:
    with get_cursor(dictionary=False) as cur:
        cur.execute("DELETE FROM records WHERE bill_date=%s", (bill_date,))
        return cur.rowcount


def delete_records_by_date_range(start_date: str, end_date: str) -> int:
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            "DELETE FROM records WHERE bill_date BETWEEN %s AND %s",
            (start_date, end_date),
        )
        return cur.rowcount


def delete_records_by_dates(dates: List[str]) -> int:
    ds = [str(d).strip() for d in (dates or []) if str(d).strip()]
    if not ds:
        return 0
    placeholders = ",".join(["%s"] * len(ds))
    with get_cursor(dictionary=False) as cur:
        cur.execute("DELETE FROM records WHERE bill_date IN ({})".format(placeholders), tuple(ds))
        return cur.rowcount


def list_available_years() -> List[int]:
    with get_cursor() as cur:
        cur.execute("SELECT DISTINCT YEAR(bill_date) AS y FROM records ORDER BY y DESC")
        return [int(x["y"]) for x in cur.fetchall() if x.get("y") is not None]


def daily_heatmap_data(year: int) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT bill_date,
                   ROUND(SUM(amount), 2) AS total_amount,
                   ROUND(SUM(CASE WHEN direction='支出' THEN amount ELSE 0 END), 2) AS expense,
                   ROUND(SUM(CASE WHEN direction='收入' THEN amount ELSE 0 END), 2) AS income
            FROM records
            WHERE YEAR(bill_date)=%s
            GROUP BY bill_date
            ORDER BY bill_date
            """,
            (year,),
        )
        return cur.fetchall()


def list_bill_dates() -> List[str]:
    with get_cursor() as cur:
        cur.execute("SELECT DISTINCT bill_date FROM records WHERE bill_date IS NOT NULL ORDER BY bill_date DESC")
        return [str(x.get("bill_date")) for x in cur.fetchall() if x.get("bill_date") is not None]


def list_categories(year: Optional[int] = None, direction: str = "") -> List[str]:
    where = []
    args: List[Any] = []
    if year is not None:
        where.append("YEAR(bill_date)=%s")
        args.append(int(year))
    if direction in ("收入", "支出"):
        where.append("direction=%s")
        args.append(direction)
    sql = "SELECT DISTINCT category FROM records"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category"
    with get_cursor() as cur:
        cur.execute(sql, tuple(args))
        return [str(x.get("category", "")) for x in cur.fetchall() if str(x.get("category", "")).strip()]


def list_l1_categories(year: Optional[int] = None, direction: str = "") -> List[str]:
    where = []
    args: List[Any] = []
    if year is not None:
        where.append("YEAR(bill_date)=%s")
        args.append(int(year))
    if direction in ("收入", "支出"):
        where.append("direction=%s")
        args.append(direction)
    sql = "SELECT DISTINCT category_l1 FROM records"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category_l1"
    with get_cursor() as cur:
        cur.execute(sql, tuple(args))
        return [str(x.get("category_l1", "")) for x in cur.fetchall() if str(x.get("category_l1", "")).strip()]


def summary_by_category_month(year: int, direction: str = "", categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    where = ["YEAR(bill_date)=%s"]
    args: List[Any] = [int(year)]
    if direction in ("收入", "支出"):
        where.append("direction=%s")
        args.append(direction)
    cats = [str(c).strip() for c in (categories or []) if str(c).strip()]
    if cats:
        placeholders = ",".join(["%s"] * len(cats))
        where.append("category IN ({})".format(placeholders))
        args.extend(cats)
    with get_cursor() as cur:
        if cats:
            # 选了类型：展示类型维度
            cur.execute(
                """
                SELECT DATE_FORMAT(bill_date, '%Y-%m') AS month,
                       direction,
                       category_l1,
                       category,
                       ROUND(SUM(amount), 2) AS total_amount
                FROM records
                WHERE {}
                GROUP BY DATE_FORMAT(bill_date, '%Y-%m'), direction, category_l1, category
                ORDER BY month DESC, direction, total_amount DESC, category_l1, category
                """.format(" AND ".join(where)),
                tuple(args),
            )
        else:
            # 未选类型：只按 月份+方向 汇总，不显示类型维度
            cur.execute(
                """
                SELECT DATE_FORMAT(bill_date, '%Y-%m') AS month,
                       direction,
                       '' AS category_l1,
                       '' AS category,
                       ROUND(SUM(amount), 2) AS total_amount
                FROM records
                WHERE {}
                GROUP BY DATE_FORMAT(bill_date, '%Y-%m'), direction
                ORDER BY month DESC, direction
                """.format(" AND ".join(where)),
                tuple(args),
            )
        return cur.fetchall()


def overview_stats() -> Dict[str, Any]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
              COUNT(*) AS total_count,
              COALESCE(SUM(CASE WHEN direction='收入' THEN amount ELSE 0 END), 0) AS total_income,
              COALESCE(SUM(CASE WHEN direction='支出' THEN amount ELSE 0 END), 0) AS total_expense
            FROM records
            """
        )
        row = cur.fetchone() or {}
        row["net"] = float(row.get("total_income", 0)) - float(row.get("total_expense", 0))
        return row


def summary_by_year() -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT YEAR(bill_date) AS year,
                   direction,
                   ROUND(SUM(amount), 2) AS total
            FROM records
            GROUP BY YEAR(bill_date), direction
            ORDER BY YEAR(bill_date) DESC, direction
            """
        )
        return cur.fetchall()


def summary_by_month() -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT DATE_FORMAT(bill_date, '%Y-%m') AS month,
                   direction,
                   ROUND(SUM(amount), 2) AS total
            FROM records
            GROUP BY DATE_FORMAT(bill_date, '%Y-%m'), direction
            ORDER BY month DESC, direction
            """
        )
        return cur.fetchall()


def summary_by_day(limit: int = 120) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT bill_date, direction, ROUND(SUM(amount), 2) AS total
            FROM records
            GROUP BY bill_date, direction
            ORDER BY bill_date DESC, direction
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


def travel_summary() -> Dict[str, List[Dict[str, Any]]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(NULLIF(travel_tag,''),'未命名行程') AS travel_tag,
                   GROUP_CONCAT(CASE WHEN travel_companions='' THEN NULL ELSE travel_companions END, '、') AS travel_companions,
                   ROUND(SUM(CASE WHEN direction='支出' THEN amount ELSE 0 END), 2) AS expense,
                   ROUND(SUM(CASE WHEN direction='收入' THEN amount ELSE 0 END), 2) AS income,
                   COUNT(*) AS record_count,
                   MIN(bill_date) AS start_date,
                   MAX(bill_date) AS end_date,
                   CAST(julianday(MAX(bill_date)) - julianday(MIN(bill_date)) AS INTEGER) + 1 AS duration_days
            FROM records
            WHERE is_travel=1
            GROUP BY COALESCE(NULLIF(travel_tag,''),'未命名行程')
            ORDER BY expense DESC
            """
        )
        by_trip = cur.fetchall()

        cur.execute(
            """
            SELECT strftime('%Y-%m', bill_date) AS month,
                   ROUND(SUM(CASE WHEN is_travel=1 AND direction='支出' THEN amount ELSE 0 END), 2) AS travel_expense,
                   ROUND(SUM(CASE WHEN is_travel=0 AND direction='支出' THEN amount ELSE 0 END), 2) AS normal_expense
            FROM records
            GROUP BY strftime('%Y-%m', bill_date)
            ORDER BY month DESC
            """
        )
        by_month = cur.fetchall()

        cur.execute(
            """
            SELECT category, ROUND(SUM(amount), 2) AS expense
            FROM records
            WHERE is_travel=1 AND direction='支出'
            GROUP BY category
            ORDER BY expense DESC
            LIMIT 12
            """
        )
        by_category = cur.fetchall()

    return {"by_trip": by_trip, "by_month": by_month, "by_category": by_category}


def set_travel_tag_by_date_range(start_date: str, end_date: str, tag: str) -> int:
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            "UPDATE records SET is_travel=1, travel_tag=%s WHERE bill_date BETWEEN %s AND %s",
            (tag, start_date, end_date),
        )
        return cur.rowcount


def clear_travel_tag_by_date_range(start_date: str, end_date: str) -> int:
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            "UPDATE records SET is_travel=0, travel_tag='', travel_companions='' WHERE bill_date BETWEEN %s AND %s",
            (start_date, end_date),
        )
        return cur.rowcount


def travel_tagged_dates(limit: int = 365) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT bill_date, travel_tag, COALESCE(travel_companions,'') AS travel_companions, COUNT(*) AS record_count,
                   ROUND(SUM(CASE WHEN direction='支出' THEN amount ELSE 0 END), 2) AS expense,
                   ROUND(SUM(CASE WHEN direction='收入' THEN amount ELSE 0 END), 2) AS income
            FROM records
            WHERE is_travel=1
            GROUP BY bill_date, travel_tag, COALESCE(travel_companions,'')
            ORDER BY bill_date DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


def set_travel_tag_by_dates(dates: List[str], tag: str, companions: str = "") -> int:
    ds = [str(d).strip() for d in (dates or []) if str(d).strip()]
    if not ds:
        return 0
    placeholders = ",".join(["%s"] * len(ds))
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            "UPDATE records SET is_travel=1, travel_tag=%s, travel_companions=%s WHERE bill_date IN ({})".format(placeholders),
            tuple([tag, companions] + ds),
        )
        return cur.rowcount


def clear_travel_tag_by_dates(dates: List[str]) -> int:
    ds = [str(d).strip() for d in (dates or []) if str(d).strip()]
    if not ds:
        return 0
    placeholders = ",".join(["%s"] * len(ds))
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            "UPDATE records SET is_travel=0, travel_tag='', travel_companions='' WHERE bill_date IN ({})".format(placeholders),
            tuple(ds),
        )
        return cur.rowcount


def update_travel_companions_by_trip_tag(travel_tag: str, companions: str) -> int:
    tag = str(travel_tag or "").strip()
    with get_cursor(dictionary=False) as cur:
        cur.execute(
            """
            UPDATE records
            SET travel_companions=%s
            WHERE is_travel=1
              AND COALESCE(NULLIF(travel_tag,''), '未命名行程')=%s
            """,
            (str(companions or "")[:255], tag),
        )
        return cur.rowcount


def backfill_category_l1(l2_to_l1_map: Dict[str, str]) -> int:
    """批量回填 category_l1（用于数据迁移）。"""
    if not l2_to_l1_map:
        return 0
    total = 0
    with get_cursor(dictionary=False) as cur:
        for l2, l1 in l2_to_l1_map.items():
            cur.execute(
                "UPDATE records SET category_l1=%s WHERE category=%s AND (category_l1='' OR category_l1 IS NULL)",
                (l1, l2),
            )
            total += cur.rowcount
    return total
