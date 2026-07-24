"""定点提醒时间计算。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta


def parse_hhmm(text: str) -> tuple[int, int]:
    parts = text.strip().split(":")
    if len(parts) != 2:
        raise ValueError("时间格式应为 HH:MM")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("时间范围无效")
    return hour, minute


def format_hhmm(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def day_slots(target_date: date, start_h: int, start_m: int, interval_hours: float) -> list[datetime]:
    slots: list[datetime] = []
    current = datetime.combine(target_date, time(start_h, start_m))
    end = datetime.combine(target_date, time(23, 59, 59))
    step = timedelta(hours=interval_hours)
    while current <= end:
        slots.append(current)
        current += step
    return slots


def find_next_slot(now: datetime, start_h: int, start_m: int, interval_hours: float) -> datetime:
    """返回严格晚于当前时刻的下一个提醒时间点。"""
    for day_offset in range(0, 3):
        target = now.date() + timedelta(days=day_offset)
        for slot in day_slots(target, start_h, start_m, interval_hours):
            if slot > now:
                return slot
    return now + timedelta(hours=interval_hours)


def slot_after(current: datetime, start_h: int, start_m: int, interval_hours: float) -> datetime:
    """返回某个时间点之后的下一个定点。"""
    for day_offset in range(0, 2):
        target = current.date() + timedelta(days=day_offset)
        for slot in day_slots(target, start_h, start_m, interval_hours):
            if slot > current:
                return slot
    return current + timedelta(hours=interval_hours)


def today_slots_preview(start_h: int, start_m: int, interval_hours: float, limit: int = 8) -> str:
    slots = day_slots(date.today(), start_h, start_m, interval_hours)
    labels = [s.strftime("%H:%M") for s in slots[:limit]]
    suffix = " …" if len(slots) > limit else ""
    return "、".join(labels) + suffix
