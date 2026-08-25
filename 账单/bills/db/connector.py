"""SQLite 连接（本地账单库，无需 MySQL）。"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# 账单/bills/db/connector.py → 仓库根
_SITE_ROOT = Path(__file__).resolve().parents[3]

DB_PATH = Path(
    os.environ.get("BILL_DB_PATH")
    or (Path(os.environ["BILL_DATA_DIR"]) / "bills.db" if os.environ.get("BILL_DATA_DIR") else None)
    or (_SITE_ROOT / "账单" / "数据" / "bills.db")
)


def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class CursorProxy:
    """把 MySQL 风格 %s 占位符转成 SQLite 的 ?。"""

    def __init__(self, cur: sqlite3.Cursor):
        self._cur = cur

    def execute(self, sql, params=None):
        sql = _adapt_sql(sql)
        if params is None:
            return self._cur.execute(sql)
        return self._cur.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        sql = _adapt_sql(sql)
        return self._cur.executemany(sql, seq_of_params)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount


def _adapt_sql(sql: str) -> str:
    # MySQL → SQLite 常用函数
    sql = re.sub(r"\bNOW\(\)", "datetime('now','localtime')", sql, flags=re.IGNORECASE)
    sql = re.sub(
        r"YEAR\s*\(\s*([a-zA-Z0-9_.]+)\s*\)",
        r"CAST(strftime('%Y', \1) AS INTEGER)",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"DATE_FORMAT\s*\(\s*([a-zA-Z0-9_.]+)\s*,\s*'%Y-%m'\s*\)",
        r"strftime('%Y-%m', \1)",
        sql,
        flags=re.IGNORECASE,
    )
    # %s → ? （避免替换字符串字面量中的 %，这里 SQL 仅用参数占位）
    sql = sql.replace("%s", "?")
    return sql


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_cursor(dictionary=True):
    conn = get_connection()
    if dictionary:
        conn.row_factory = _dict_factory
    raw = conn.cursor()
    cur = CursorProxy(raw)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
