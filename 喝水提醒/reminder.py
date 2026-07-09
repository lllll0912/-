"""定时提醒调度 — 按每日定点时间触发。"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from data_store import DataStore
from schedule_util import find_next_slot, parse_hhmm, slot_after


class ReminderScheduler:
    def __init__(
        self,
        root,
        store: DataStore,
        on_remind: Callable[[datetime, datetime], None],
    ) -> None:
        self.root = root
        self.store = store
        self.on_remind = on_remind
        self._after_id: str | None = None
        self.next_reminder_at: datetime | None = None
        self._paused = False
        self._pending_next: datetime | None = None

    def _settings_tuple(self) -> tuple[int, int, float]:
        s = self.store.settings
        h, m = parse_hhmm(s.schedule_start)
        return h, m, s.schedule_interval_hours

    def start(self) -> None:
        self.stop()
        self._paused = False
        self._pending_next = None
        if not self.store.settings.reminder_enabled:
            self.next_reminder_at = None
            return

        now = datetime.now()
        h, m, interval = self._settings_tuple()
        self._schedule_at(find_next_slot(now, h, m, interval))

    def stop(self) -> None:
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def reschedule(self) -> None:
        """设置变更后，按定点规则重新计算下一次提醒。"""
        self.start()

    def pause(self) -> None:
        self.stop()
        self._paused = True

    def continue_to_next(self, next_slot: datetime | None = None) -> None:
        """提醒处理完毕后，等待下一个定点。"""
        self._paused = False
        if not self.store.settings.reminder_enabled:
            self.next_reminder_at = None
            return

        target = next_slot or self._pending_next
        if target is None:
            self.start()
            return

        now = datetime.now()
        h, m, interval = self._settings_tuple()
        if target <= now:
            target = find_next_slot(now, h, m, interval)
        self._schedule_at(target)
        self._pending_next = None

    def _schedule_at(self, slot: datetime) -> None:
        self.next_reminder_at = slot
        delay_ms = max(0, int((slot - datetime.now()).total_seconds() * 1000))
        self._after_id = self.root.after(delay_ms, self._fire)

    def _fire(self) -> None:
        now = datetime.now()
        self._after_id = None
        fired_slot = self.next_reminder_at or now
        h, m, interval = self._settings_tuple()
        self._pending_next = slot_after(fired_slot, h, m, interval)
        self.next_reminder_at = None
        self._paused = True
        self.on_remind(now, self._pending_next)

    def remaining_seconds(self) -> int | None:
        if self._paused or self.next_reminder_at is None:
            return None
        return max(0, int((self.next_reminder_at - datetime.now()).total_seconds()))

    def format_countdown(self) -> str:
        seconds = self.remaining_seconds()
        if seconds is None:
            if not self.store.settings.reminder_enabled:
                return "已暂停"
            return "--:--"
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def format_next_time(self) -> str:
        if self.next_reminder_at is None:
            return "未设置"
        return self.next_reminder_at.strftime("%H:%M")
