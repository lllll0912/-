from db.connector import get_cursor


DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS import_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_name TEXT NOT NULL DEFAULT '',
        source_year INTEGER NOT NULL,
        raw_text TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        confirmed_at TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS staging_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        row_index INTEGER NOT NULL,
        bill_date TEXT NULL,
        amount REAL NOT NULL DEFAULT 0,
        detail TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '',
        direction TEXT NOT NULL DEFAULT '支出',
        category_l1 TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '其他消费',
        is_travel INTEGER NOT NULL DEFAULT 0,
        travel_tag TEXT NOT NULL DEFAULT '',
        is_valid INTEGER NOT NULL DEFAULT 1,
        error_msg TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bill_date TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        detail TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        direction TEXT NOT NULL DEFAULT '支出',
        category_l1 TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '其他消费',
        is_travel INTEGER NOT NULL DEFAULT 0,
        travel_tag TEXT NOT NULL DEFAULT '',
        travel_companions TEXT NOT NULL DEFAULT '',
        source_batch_id INTEGER NULL,
        inserted_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
    """,
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_records_date ON records(bill_date)",
    "CREATE INDEX IF NOT EXISTS idx_records_travel ON records(is_travel, travel_tag)",
    "CREATE INDEX IF NOT EXISTS idx_records_direction ON records(direction)",
    "CREATE INDEX IF NOT EXISTS idx_records_cat_l1 ON records(category_l1)",
]

_MIGRATIONS = [
    "ALTER TABLE records ADD COLUMN travel_companions TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE records ADD COLUMN category_l1 TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE staging_records ADD COLUMN category_l1 TEXT NOT NULL DEFAULT ''",
]


def init_db():
    with get_cursor(dictionary=False) as cur:
        for ddl in DDL_STATEMENTS:
            cur.execute(ddl)
        for sql in _INDEXES:
            cur.execute(sql)
        for sql in _MIGRATIONS:
            try:
                cur.execute(sql)
            except Exception:
                pass
