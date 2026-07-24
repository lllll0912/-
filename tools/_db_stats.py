import sqlite3
import sys
from pathlib import Path

p = Path(sys.argv[1] if len(sys.argv) > 1 else "data/bills.db")
print("path", p.resolve())
print("exists", p.exists(), "size", p.stat().st_size if p.exists() else 0)
if not p.exists():
    raise SystemExit(1)
c = sqlite3.connect(str(p))
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
print("tables", tables)
for t in tables:
    n = c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    print(f"  {t}: {n}")
if "records" in tables:
    row = c.execute(
        "SELECT MIN(bill_date), MAX(bill_date), COUNT(*) FROM records"
    ).fetchone()
    print("records_date_range", row)
c.close()
