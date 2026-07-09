"""喝水记录与设置的本地持久化。"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_FILE = DATA_DIR / "water_data.json"


@dataclass
class Settings:
    schedule_start: str = "09:30"
    schedule_interval_hours: float = 1.5
    cup_ml: int = 250
    daily_goal_ml: int = 2000
    reminder_enabled: bool = True


@dataclass
class WaterRecord:
    id: str
    timestamp: str
    amount_ml: int
    unit: str
    raw_amount: float


class DataStore:
    def __init__(self, path: Path = DATA_FILE) -> None:
        self.path = path
        self.settings = Settings()
        self.records: list[WaterRecord] = []
        self._load()

    def _load(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save()
            return

        with self.path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        settings_data = payload.get("settings", {})
        self.settings = Settings(
            schedule_start=settings_data.get("schedule_start", "09:30"),
            schedule_interval_hours=float(settings_data.get("schedule_interval_hours", 1.5)),
            cup_ml=int(settings_data.get("cup_ml", 250)),
            daily_goal_ml=int(settings_data.get("daily_goal_ml", 2000)),
            reminder_enabled=bool(settings_data.get("reminder_enabled", True)),
        )

        self.records = []
        for item in payload.get("records", []):
            self.records.append(
                WaterRecord(
                    id=item.get("id") or str(uuid.uuid4()),
                    timestamp=item["timestamp"],
                    amount_ml=int(item["amount_ml"]),
                    unit=item.get("unit", "ml"),
                    raw_amount=float(item.get("raw_amount", item["amount_ml"])),
                )
            )
        self._save()

    def _save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "settings": asdict(self.settings),
            "records": [asdict(r) for r in self.records],
        }
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def update_settings(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self._save()

    def add_record(self, amount_ml: int, unit: str, raw_amount: float) -> WaterRecord:
        record = WaterRecord(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(timespec="seconds"),
            amount_ml=amount_ml,
            unit=unit,
            raw_amount=raw_amount,
        )
        self.records.append(record)
        self._save()
        return record

    def get_record(self, record_id: str) -> WaterRecord | None:
        for record in self.records:
            if record.id == record_id:
                return record
        return None

    def update_record(self, record_id: str, amount_ml: int, unit: str, raw_amount: float) -> bool:
        record = self.get_record(record_id)
        if record is None:
            return False
        record.amount_ml = amount_ml
        record.unit = unit
        record.raw_amount = raw_amount
        self._save()
        return True

    def delete_record(self, record_id: str) -> bool:
        before = len(self.records)
        self.records = [r for r in self.records if r.id != record_id]
        if len(self.records) == before:
            return False
        self._save()
        return True

    def daily_total_ml(self, target_date: date | None = None) -> int:
        target = target_date or date.today()
        total = 0
        for record in self.records:
            record_date = datetime.fromisoformat(record.timestamp).date()
            if record_date == target:
                total += record.amount_ml
        return total

    def records_on_date(self, target_date: date) -> list[WaterRecord]:
        return [
            r
            for r in self.records
            if datetime.fromisoformat(r.timestamp).date() == target_date
        ]

    def aggregate_by_period(self, period: str) -> list[dict[str, Any]]:
        """按日/周/月聚合饮水总量。"""
        buckets: dict[str, int] = {}

        for record in self.records:
            dt = datetime.fromisoformat(record.timestamp)
            if period == "day":
                key = dt.strftime("%Y-%m-%d")
            elif period == "week":
                year, week, _ = dt.isocalendar()
                key = f"{year}-W{week:02d}"
            elif period == "month":
                key = dt.strftime("%Y-%m")
            else:
                raise ValueError(f"未知周期: {period}")
            buckets[key] = buckets.get(key, 0) + record.amount_ml

        sorted_keys = sorted(buckets.keys())
        return [{"label": key, "total_ml": buckets[key]} for key in sorted_keys]

    def average_by_period(self, period: str) -> list[dict[str, Any]]:
        """计算每个周期内的日均饮水量（周/月）或当日总量（日）。"""
        if period == "day":
            return self.aggregate_by_period("day")

        day_buckets: dict[str, dict[str, int]] = {}
        for record in self.records:
            dt = datetime.fromisoformat(record.timestamp)
            if period == "week":
                year, week, _ = dt.isocalendar()
                key = f"{year}-W{week:02d}"
            elif period == "month":
                key = dt.strftime("%Y-%m")
            else:
                raise ValueError(f"未知周期: {period}")

            day_key = dt.strftime("%Y-%m-%d")
            if key not in day_buckets:
                day_buckets[key] = {}
            day_buckets[key][day_key] = day_buckets[key].get(day_key, 0) + record.amount_ml

        result: list[dict[str, Any]] = []
        for key in sorted(day_buckets.keys()):
            daily_values = list(day_buckets[key].values())
            avg = sum(daily_values) / len(daily_values) if daily_values else 0
            result.append({"label": key, "total_ml": int(round(avg))})
        return result
