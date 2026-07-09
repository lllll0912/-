import mysql.connector
from contextlib import contextmanager

DB_CFG = dict(
    host="localhost",
    user="root",
    password="245801",
    database="teacher_db",
    charset="utf8mb4",
)


def get_connection(use_database=True):
    cfg = dict(DB_CFG)
    if not use_database:
        cfg.pop("database", None)
    return mysql.connector.connect(**cfg)


@contextmanager
def get_cursor(dictionary=True):
    conn = get_connection(use_database=True)
    cur = conn.cursor(dictionary=dictionary)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

