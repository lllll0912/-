import mysql.connector
from contextlib import contextmanager

DB_CFG = dict(
    host="localhost",
    user="root",
    password="245801",
    database="teacher_db",
    charset="utf8mb4",
)


@contextmanager
def get_cursor():
    conn = mysql.connector.connect(**DB_CFG)
    cur = conn.cursor(dictionary=True)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

