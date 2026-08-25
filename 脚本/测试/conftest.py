# 让 unittest 能找到 modules/bills、modules/poems
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "modules" / "bills", ROOT / "modules" / "poems"):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)
