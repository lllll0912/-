"""设置与高级功能窗口。"""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk

from charts import ChartWindow
from data_store import DataStore
from records_editor import RecordEditDialog
from schedule_util import parse_hhmm, today_slots_preview
from theme import COLORS, create_card, fade_in_window, setup_theme


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc, store: DataStore, on_saved) -> None:
        super().__init__(parent)
        self.store = store
        self.on_saved = on_saved
        self._chart_window: ChartWindow | None = None

        self.title("设置与管理")
        self.geometry("560x640")
        self.minsize(520, 580)
        self.configure(bg=COLORS["bg"])
        setup_theme(self)

        settings = store.settings
        self.schedule_start_var = tk.StringVar(value=settings.schedule_start)
        self.schedule_interval_var = tk.StringVar(value=str(settings.schedule_interval_hours))
        self.cup_ml_var = tk.StringVar(value=str(settings.cup_ml))
        self.goal_ml_var = tk.StringVar(value=str(settings.daily_goal_ml))
        self.enabled_var = tk.BooleanVar(value=settings.reminder_enabled)
        self.preview_var = tk.StringVar()

        self._build_ui()
        self._update_preview()
        self.transient(parent)
        fade_in_window(self)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="设置与管理", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 16))

        settings_frame = create_card(outer, "定点提醒", padding=14)
        settings_frame.pack(fill=tk.X, pady=(0, 12))

        start_row = ttk.Frame(settings_frame, style="Card.TFrame")
        start_row.pack(fill=tk.X, pady=4)
        ttk.Label(start_row, text="每日开始", style="Card.TLabel", width=10).pack(side=tk.LEFT)
        ttk.Entry(start_row, textvariable=self.schedule_start_var, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Label(start_row, text="如 09:30", style="CardMuted.TLabel").pack(side=tk.LEFT)

        interval_row = ttk.Frame(settings_frame, style="Card.TFrame")
        interval_row.pack(fill=tk.X, pady=4)
        ttk.Label(interval_row, text="提醒间隔", style="Card.TLabel", width=10).pack(side=tk.LEFT)
        ttk.Entry(interval_row, textvariable=self.schedule_interval_var, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Label(interval_row, text="小时（如 1.5）", style="CardMuted.TLabel").pack(side=tk.LEFT)

        ttk.Label(
            settings_frame,
            textvariable=self.preview_var,
            style="CardMuted.TLabel",
            wraplength=460,
        ).pack(anchor=tk.W, pady=(8, 0))

        cup_row = ttk.Frame(settings_frame, style="Card.TFrame")
        cup_row.pack(fill=tk.X, pady=(10, 4))
        ttk.Label(cup_row, text="每杯水量", style="Card.TLabel", width=10).pack(side=tk.LEFT)
        ttk.Entry(cup_row, textvariable=self.cup_ml_var, width=8).pack(side=tk.LEFT, padx=6)
        ttk.Label(cup_row, text="ml", style="CardMuted.TLabel").pack(side=tk.LEFT)

        goal_row = ttk.Frame(settings_frame, style="Card.TFrame")
        goal_row.pack(fill=tk.X, pady=4)
        ttk.Label(goal_row, text="每日目标", style="Card.TLabel", width=10).pack(side=tk.LEFT)
        ttk.Entry(goal_row, textvariable=self.goal_ml_var, width=8).pack(side=tk.LEFT, padx=6)
        ttk.Label(goal_row, text="ml", style="CardMuted.TLabel").pack(side=tk.LEFT)

        ttk.Checkbutton(settings_frame, text="启用定点提醒", variable=self.enabled_var).pack(anchor=tk.W, pady=(10, 0))
        ttk.Label(
            settings_frame,
            text="提醒按固定时间点触发，点击「喝了一杯」不会重置计时。",
            style="CardMuted.TLabel",
            wraplength=460,
        ).pack(anchor=tk.W, pady=(8, 0))
        ttk.Button(settings_frame, text="保存设置", style="Accent.TButton", command=self._save_settings).pack(
            anchor=tk.W, pady=(12, 0)
        )

        records_card = create_card(outer, "今日记录", padding=12)
        records_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        self.records_summary_var = tk.StringVar()
        ttk.Label(records_card, textvariable=self.records_summary_var, style="CardMuted.TLabel").pack(
            anchor=tk.W, pady=(0, 8)
        )

        columns = ("time", "detail", "ml")
        self.today_tree = ttk.Treeview(records_card, columns=columns, show="headings", height=8)
        self.today_tree.heading("time", text="时间")
        self.today_tree.heading("detail", text="记录")
        self.today_tree.heading("ml", text="ml")
        self.today_tree.column("time", width=80, anchor=tk.CENTER)
        self.today_tree.column("detail", width=120, anchor=tk.CENTER)
        self.today_tree.column("ml", width=60, anchor=tk.CENTER)
        self.today_tree.pack(fill=tk.BOTH, expand=True)
        self.today_tree.bind("<Double-1>", lambda _e: self._edit_selected())

        actions = ttk.Frame(records_card, style="Card.TFrame")
        actions.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(actions, text="编辑", style="Ghost.TButton", command=self._edit_selected).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, text="删除", style="Danger.TButton", command=self._delete_selected).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, text="统计图表", style="Ghost.TButton", command=self._open_charts).pack(side=tk.RIGHT)

        self._reload_records()

    def _update_preview(self) -> None:
        try:
            h, m = parse_hhmm(self.schedule_start_var.get())
            interval = float(self.schedule_interval_var.get())
            preview = today_slots_preview(h, m, interval)
            self.preview_var.set(f"今日提醒时刻：{preview}")
        except (ValueError, TypeError):
            self.preview_var.set("今日提醒时刻：请填写有效的时间和间隔")

    def _reload_records(self) -> None:
        for item in self.today_tree.get_children():
            self.today_tree.delete(item)

        today = date.today()
        records = sorted(self.store.records_on_date(today), key=lambda r: r.timestamp, reverse=True)
        for record in records:
            dt = datetime.fromisoformat(record.timestamp)
            unit_label = "杯" if record.unit == "cup" else "ml"
            self.today_tree.insert(
                "",
                tk.END,
                iid=record.id,
                values=(dt.strftime("%H:%M:%S"), f"{record.raw_amount} {unit_label}", record.amount_ml),
            )
        total = self.store.daily_total_ml(today)
        self.records_summary_var.set(f"今日 {len(records)} 条 · 合计 {total} ml")

    def _save_settings(self) -> None:
        try:
            parse_hhmm(self.schedule_start_var.get())
            interval = float(self.schedule_interval_var.get().strip())
            cup_ml = int(self.cup_ml_var.get().strip())
            goal_ml = int(self.goal_ml_var.get().strip())
        except ValueError:
            messagebox.showerror("设置错误", "请检查时间格式（HH:MM）和数值。", parent=self)
            return

        if interval <= 0 or cup_ml <= 0 or goal_ml <= 0:
            messagebox.showerror("设置错误", "间隔和水量必须大于 0。", parent=self)
            return

        self.store.update_settings(
            schedule_start=self.schedule_start_var.get().strip(),
            schedule_interval_hours=interval,
            cup_ml=cup_ml,
            daily_goal_ml=goal_ml,
            reminder_enabled=self.enabled_var.get(),
        )
        self._update_preview()
        self.on_saved()
        self._reload_records()
        messagebox.showinfo("已保存", "定点提醒已更新。", parent=self)

    def _get_selected_id(self) -> str | None:
        selected = self.today_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择一条记录。", parent=self)
            return None
        return selected[0]

    def _edit_selected(self) -> None:
        record_id = self._get_selected_id()
        if not record_id:
            return
        record = self.store.get_record(record_id)
        if record is None:
            self._reload_records()
            return

        def _after() -> None:
            self._reload_records()
            self.on_saved()

        RecordEditDialog(self, self.store, record, _after)

    def _delete_selected(self) -> None:
        record_id = self._get_selected_id()
        if not record_id:
            return
        record = self.store.get_record(record_id)
        if record is None:
            self._reload_records()
            return
        if not messagebox.askyesno("确认删除", f"删除 {record.amount_ml} ml 的记录？", parent=self):
            return
        if self.store.delete_record(record_id):
            self._reload_records()
            self.on_saved()

    def _open_charts(self) -> None:
        if self._chart_window is not None and self._chart_window.winfo_exists():
            self._chart_window.lift()
            self._chart_window._render_chart()
            return
        self._chart_window = ChartWindow(self, self.store)

    def refresh(self) -> None:
        if self.winfo_exists():
            self._reload_records()
            self._update_preview()
