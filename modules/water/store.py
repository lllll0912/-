"""喝水记录与设置（网站版，JSON 持久化）。"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


def _default_data_path() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / "water_data.json"
    site_root = Path(__file__).resolve().parents[2]
    return site_root / "data" / "water_data.json"


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
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _default_data_path()
        self.settings = Settings()
        self.records: list[WaterRecord] = []
        self._load()

    def _load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
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

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
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

    def add_record(self, amount_ml: int, unit: str = "ml", raw_amount: float | None = None) -> WaterRecord:
        record = WaterRecord(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(timespec="seconds"),
            amount_ml=amount_ml,
            unit=unit,
            raw_amount=float(raw_amount if raw_amount is not None else amount_ml),
        )
        self.records.append(record)
        self._save()
        return record

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

    def records_on_date(self, target_date: date | None = None) -> list[WaterRecord]:
        target = target_date or date.today()
        return [
            r
            for r in self.records
            if datetime.fromisoformat(r.timestamp).date() == target
        ]

    def aggregate_by_day(self, limit: int = 30) -> list[dict[str, Any]]:
        buckets: dict[str, int] = {}
        for record in self.records:
            key = datetime.fromisoformat(record.timestamp).strftime("%Y-%m-%d")
            buckets[key] = buckets.get(key, 0) + record.amount_ml
        keys = sorted(buckets.keys())[-limit:]
        return [{"label": k, "total_ml": buckets[k]} for k in keys]
