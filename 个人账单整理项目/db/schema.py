from db.connector import get_connection, get_cursor


DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS import_batches (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        source_name VARCHAR(255) NOT NULL DEFAULT '',
        source_year INT NOT NULL,
        raw_text LONGTEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'draft',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        confirmed_at DATETIME NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS staging_records (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        batch_id BIGINT NOT NULL,
        row_index INT NOT NULL,
        bill_date DATE NULL,
        amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        detail VARCHAR(255) NOT NULL DEFAULT '',
        note TEXT NOT NULL,
        direction VARCHAR(10) NOT NULL DEFAULT '支出',
        category_l1 VARCHAR(50) NOT NULL DEFAULT '',
        category VARCHAR(50) NOT NULL DEFAULT '其他消费',
        is_travel TINYINT(1) NOT NULL DEFAULT 0,
        travel_tag VARCHAR(100) NOT NULL DEFAULT '',
        is_valid TINYINT(1) NOT NULL DEFAULT 1,
        error_msg VARCHAR(255) NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_staging_batch FOREIGN KEY (batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS records (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        bill_date DATE NOT NULL,
        amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        detail VARCHAR(255) NOT NULL,
        note TEXT NOT NULL,
        direction VARCHAR(10) NOT NULL DEFAULT '支出',
        category_l1 VARCHAR(50) NOT NULL DEFAULT '',
        category VARCHAR(50) NOT NULL DEFAULT '其他消费',
        is_travel TINYINT(1) NOT NULL DEFAULT 0,
        travel_tag VARCHAR(100) NOT NULL DEFAULT '',
        travel_companions VARCHAR(255) NOT NULL DEFAULT '',
        source_batch_id BIGINT NULL,
        inserted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_records_date (bill_date),
        INDEX idx_records_travel (is_travel, travel_tag),
        INDEX idx_records_direction (direction),
        INDEX idx_records_cat_l1 (category_l1)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]

_MIGRATIONS = [
    "ALTER TABLE records ADD COLUMN inserted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "ALTER TABLE records ADD COLUMN category_l1 VARCHAR(50) NOT NULL DEFAULT '' AFTER direction",
    "ALTER TABLE staging_records ADD COLUMN category_l1 VARCHAR(50) NOT NULL DEFAULT '' AFTER direction",
    "ALTER TABLE records ADD INDEX idx_records_cat_l1 (category_l1)",
    "ALTER TABLE records ADD COLUMN travel_companions VARCHAR(255) NOT NULL DEFAULT '' AFTER travel_tag",
]


def init_db():
    conn = get_connection(use_database=False)
    cur = conn.cursor()
    try:
        cur.execute("CREATE DATABASE IF NOT EXISTS teacher_db DEFAULT CHARSET utf8mb4")
        conn.commit()
    finally:
        conn.close()

    with get_cursor(dictionary=False) as cur2:
        for ddl in DDL_STATEMENTS:
            cur2.execute(ddl)
        for sql in _MIGRATIONS:
            try:
                cur2.execute(sql)
            except Exception:
                pass
