"""喝水模块时区：统一按 Asia/Shanghai 存取与展示。"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def parse_water_ts(ts: str) -> datetime:
    """解析记录时间并转到上海时区。无时区的历史数据：Fly 视为 UTC，本机视为已是上海时间。"""
    dt = datetime.fromisoformat(str(ts).strip())
    if dt.tzinfo is None:
        if (os.environ.get("BILL_DATA_DIR") or "").strip():
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.replace(tzinfo=CN_TZ)
    return dt.astimezone(CN_TZ)


def format_hm(dt: datetime) -> str:
    return dt.astimezone(CN_TZ).strftime("%H:%M")


def format_hms(dt: datetime) -> str:
    return dt.astimezone(CN_TZ).strftime("%H:%M:%S")


def format_record_clock(ts: str) -> str:
    return format_hms(parse_water_ts(ts))
