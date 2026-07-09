"""今日饮水记录编辑。"""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Callable

from data_store import DataStore, WaterRecord
from theme import COLORS, FONT_BOLD, create_card, fade_in_window, setup_theme


class RecordEditDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        store: DataStore,
        record: WaterRecord,
        on_saved: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.record = record
        self.on_saved = on_saved

        self.title("编辑饮水记录")
        self.geometry("400x340")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        setup_theme(self)

        self.unit_var = tk.StringVar(value=record.unit)
        self.amount_var = tk.StringVar(value=str(record.raw_amount))

        self._build_ui()
        self.transient(parent)
        self.grab_set()
        fade_in_window(self)

    def _build_ui(self) -> None:
        frame = create_card(self, "修改记录", padding=20)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        time_text = datetime.fromisoformat(self.record.timestamp).strftime("%H:%M:%S")
        ttk.Label(frame, text=f"记录时间：{time_text}", style="CardMuted.TLabel").pack(anchor=tk.W, pady=(0, 12))

        row = ttk.Frame(frame, style="Card.TFrame")
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="数量", style="Card.TLabel", width=8).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.amount_var, width=12).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(row, text="杯", variable=self.unit_var, value="cup").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(row, text="ml", variable=self.unit_var, value="ml").pack(side=tk.LEFT)

        ttk.Label(
            frame,
            text=f"1 杯 = {self.store.settings.cup_ml} ml",
            style="CardMuted.TLabel",
        ).pack(anchor=tk.W, pady=(8, 16))

        btns = ttk.Frame(frame, style="Card.TFrame")
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="保存修改", style="Accent.TButton", command=self._save).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btns, text="取消", style="Ghost.TButton", command=self.destroy).pack(side=tk.LEFT)
        ttk.Button(btns, text="删除记录", style="Danger.TButton", command=self._delete).pack(side=tk.RIGHT)

    def _parse_amount(self) -> tuple[int, str, float]:
        raw_text = self.amount_var.get().strip()
        if not raw_text:
            raise ValueError("请输入饮水量")
        raw_amount = float(raw_text)
        if raw_amount <= 0:
            raise ValueError("饮水量必须大于 0")
        unit = self.unit_var.get()
        if unit == "cup":
            amount_ml = int(round(raw_amount * self.store.settings.cup_ml))
        else:
            amount_ml = int(round(raw_amount))
        return amount_ml, unit, raw_amount

    def _save(self) -> None:
        try:
            amount_ml, unit, raw_amount = self._parse_amount()
        except ValueError as exc:
            messagebox.showwarning("输入有误", str(exc), parent=self)
            return

        if not self.store.update_record(self.record.id, amount_ml, unit, raw_amount):
            messagebox.showerror("保存失败", "记录不存在或已被删除。", parent=self)
            return

        self.on_saved()
        messagebox.showinfo("已更新", f"记录已修改为 {amount_ml} ml", parent=self)
        self.destroy()

    def _delete(self) -> None:
        dt = datetime.fromisoformat(self.record.timestamp).strftime("%H:%M:%S")
        if not messagebox.askyesno(
            "确认删除",
            f"确定删除 {dt} 的饮水记录（{self.record.amount_ml} ml）吗？\n删除后无法恢复。",
            parent=self,
        ):
            return

        if not self.store.delete_record(self.record.id):
            messagebox.showerror("删除失败", "记录不存在或已被删除。", parent=self)
            return

        self.on_saved()
        messagebox.showinfo("已删除", "记录已删除。", parent=self)
        self.destroy()


class RecordsEditorWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc, store: DataStore, on_changed: Callable[[], None]) -> None:
        super().__init__(parent)
        self.store = store
        self.on_changed = on_changed
        self._target_date = date.today()

        self.title("今日饮水记录")
        self.geometry("640x480")
        self.minsize(560, 420)
        self.configure(bg=COLORS["bg"])
        setup_theme(self)

        self._build_ui()
        self._reload_records()
        fade_in_window(self)

    def _build_ui(self) -> None:
        header = ttk.Frame(self, style="Soft.TFrame", padding=(20, 16))
        header.pack(fill=tk.X)

        ttk.Label(header, text="今日饮水记录", font=FONT_BOLD, background=COLORS["bg_soft"]).pack(side=tk.LEFT)
        self.summary_var = tk.StringVar()
        ttk.Label(header, textvariable=self.summary_var, style="Muted.TLabel", background=COLORS["bg_soft"]).pack(
            side=tk.RIGHT
        )

        body = create_card(self, "记录列表", padding=12)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        columns = ("time", "raw", "unit", "ml")
        self.tree = ttk.Treeview(body, columns=columns, show="headings", height=12)
        self.tree.heading("time", text="时间")
        self.tree.heading("raw", text="数量")
        self.tree.heading("unit", text="单位")
        self.tree.heading("ml", text="折合 ml")
        self.tree.column("time", width=120, anchor=tk.CENTER)
        self.tree.column("raw", width=80, anchor=tk.CENTER)
        self.tree.column("unit", width=80, anchor=tk.CENTER)
        self.tree.column("ml", width=100, anchor=tk.CENTER)

        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        actions = ttk.Frame(self, padding=(16, 0, 16, 16))
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="编辑选中", style="Accent.TButton", command=self._edit_selected).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(actions, text="删除选中", style="Danger.TButton", command=self._delete_selected).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(actions, text="刷新", style="Ghost.TButton", command=self._reload_records).pack(side=tk.LEFT)

    def _reload_records(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        records = self.store.records_on_date(self._target_date)
        for record in sorted(records, key=lambda r: r.timestamp, reverse=True):
            dt = datetime.fromisoformat(record.timestamp)
            unit_label = "杯" if record.unit == "cup" else "ml"
            self.tree.insert(
                "",
                tk.END,
                iid=record.id,
                values=(dt.strftime("%H:%M:%S"), record.raw_amount, unit_label, record.amount_ml),
            )

        total = self.store.daily_total_ml(self._target_date)
        self.summary_var.set(f"共 {len(records)} 条 · 合计 {total} ml")

    def _get_selected_record(self) -> WaterRecord | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择一条记录。", parent=self)
            return None
        record = self.store.get_record(selected[0])
        if record is None:
            messagebox.showerror("错误", "记录不存在，请刷新后重试。", parent=self)
            return None
        return record

    def _edit_selected(self) -> None:
        record = self._get_selected_record()
        if record is None:
            return

        def _after_save() -> None:
            self._reload_records()
            self.on_changed()

        RecordEditDialog(self, self.store, record, _after_save)

    def _delete_selected(self) -> None:
        record = self._get_selected_record()
        if record is None:
            return

        dt = datetime.fromisoformat(record.timestamp).strftime("%H:%M:%S")
        if not messagebox.askyesno(
            "确认删除",
            f"确定删除 {dt} 的饮水记录（{record.amount_ml} ml）吗？",
            parent=self,
        ):
            return

        if self.store.delete_record(record.id):
            self._reload_records()
            self.on_changed()
            messagebox.showinfo("已删除", "记录已删除。", parent=self)
