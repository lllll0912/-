"""喝水提醒弹窗。"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

from data_store import DataStore
from theme import COLORS, FONT_BOLD, create_card, fade_in_window, setup_theme


class ReminderPopup(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        store: DataStore,
        current_time: datetime,
        next_time: datetime,
        on_submitted: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.on_submitted = on_submitted

        self.title("该喝水啦！")
        self.geometry("460x420")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(bg=COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

        setup_theme(self)
        self.unit_var = tk.StringVar(value="cup")
        self.amount_var = tk.StringVar(value="1")
        self._pulse_on = True

        self._build_ui(current_time, next_time)
        self._center_on_screen()
        fade_in_window(self)
        self._pulse_title()

    def _center_on_screen(self) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 3
        self.geometry(f"+{x}+{y}")

    def _pulse_title(self) -> None:
        if not self._pulse_on or not self.winfo_exists():
            return
        colors = [COLORS["accent"], COLORS["accent_dark"], COLORS["success"]]
        idx = int(datetime.now().timestamp() * 2) % len(colors)
        self.title_label.configure(foreground=colors[idx])
        self.after(500, self._pulse_title)

    def _build_ui(self, current_time: datetime, next_time: datetime) -> None:
        hero = tk.Frame(self, bg=COLORS["accent_soft"], height=72)
        hero.pack(fill=tk.X)
        hero.pack_propagate(False)
        self.title_label = tk.Label(
            hero,
            text="💧  该喝水啦！",
            font=FONT_BOLD,
            bg=COLORS["accent_soft"],
            fg=COLORS["accent"],
        )
        self.title_label.pack(expand=True)

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        info = create_card(frame, "提醒信息", padding=14)
        info.pack(fill=tk.X, pady=(0, 14))

        daily_total = self.store.daily_total_ml()
        rows = [
            ("当前时间", current_time.strftime("%Y-%m-%d %H:%M:%S")),
            ("下次提醒", next_time.strftime("%Y-%m-%d %H:%M:%S")),
            ("今日累计", f"{daily_total} ml"),
        ]
        for label, value in rows:
            row = ttk.Frame(info, style="Card.TFrame")
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=label, style="CardMuted.TLabel", width=10).pack(side=tk.LEFT)
            value_style = "CardAccent.TLabel" if label == "今日累计" else "Card.TLabel"
            ttk.Label(row, text=value, style=value_style).pack(side=tk.LEFT)

        input_frame = create_card(frame, "记录本次饮水", padding=14)
        input_frame.pack(fill=tk.X, pady=(0, 16))

        row = ttk.Frame(input_frame, style="Card.TFrame")
        row.pack(fill=tk.X)
        ttk.Label(row, text="数量", style="Card.TLabel", width=6).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.amount_var, width=10).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(row, text="杯", variable=self.unit_var, value="cup").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(row, text="ml", variable=self.unit_var, value="ml").pack(side=tk.LEFT)

        ttk.Label(
            input_frame,
            text=f"1 杯 = {self.store.settings.cup_ml} ml",
            style="CardMuted.TLabel",
        ).pack(anchor=tk.W, pady=(10, 0))

        quick = ttk.Frame(input_frame, style="Card.TFrame")
        quick.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(quick, text="快捷：", style="CardMuted.TLabel").pack(side=tk.LEFT)
        for cups in (0.5, 1, 2):
            ttk.Button(
                quick,
                text=f"{cups} 杯",
                style="Ghost.TButton",
                command=lambda c=cups: self._quick_fill(c),
            ).pack(side=tk.LEFT, padx=(0, 6))

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="提交记录", style="Accent.TButton", command=self._on_submit).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(buttons, text="稍后提醒", style="Ghost.TButton", command=self._on_skip).pack(side=tk.LEFT)

    def _quick_fill(self, cups: float) -> None:
        self.unit_var.set("cup")
        self.amount_var.set(str(cups))

    def _parse_amount_ml(self) -> tuple[int, str, float]:
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

    def _on_submit(self) -> None:
        try:
            amount_ml, unit, raw_amount = self._parse_amount_ml()
        except ValueError as exc:
            messagebox.showwarning("输入有误", str(exc), parent=self)
            return

        self.store.add_record(amount_ml=amount_ml, unit=unit, raw_amount=raw_amount)
        self.on_submitted()
        messagebox.showinfo("记录成功", f"已记录 {amount_ml} ml，继续保持！", parent=self)
        self._pulse_on = False
        self.destroy()

    def _on_skip(self) -> None:
        self._pulse_on = False
        self.destroy()
