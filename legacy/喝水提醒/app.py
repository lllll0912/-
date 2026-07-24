"""喝水提醒主应用 — 悬浮小窗 + 定点放大提醒。"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from data_store import DataStore
from icon_util import apply_window_icon
from reminder import ReminderScheduler
from settings_window import SettingsWindow
from charts import ChartWindow
from theme import COLORS, FONT_BOLD, create_card, fade_in_window, setup_theme

COMPACT_DEFAULT = (300, 268)
COMPACT_MIN = (260, 220)
EXPANDED_SIZE = (420, 500)

FONT_COUNTDOWN = ("Microsoft YaHei UI", 32, "bold")
FONT_DRINK_BTN = ("Microsoft YaHei UI", 17, "bold")
FONT_DRINK_FLASH = ("Microsoft YaHei UI", 15, "bold")
FONT_COMPACT_INFO = ("Microsoft YaHei UI", 10)


class WaterReminderApp:
    MODE_COMPACT = "compact"
    MODE_REMINDER = "reminder"

    def __init__(self) -> None:
        self.root = tk.Tk()
        setup_theme(self.root)
        apply_window_icon(self.root)
        self.store = DataStore()
        self.scheduler = ReminderScheduler(self.root, self.store, self._on_timer_due)
        self._settings_window: SettingsWindow | None = None
        self._chart_window: ChartWindow | None = None
        self._mode = self.MODE_COMPACT
        self._drag_offset = (0, 0)
        self._pending_next_slot: datetime | None = None
        self._saved_compact_geometry: str | None = None
        self._compact_initialized = False

        self.countdown_var = tk.StringVar()
        self.daily_var = tk.StringVar()
        self.next_slot_var = tk.StringVar()
        self.hint_var = tk.StringVar(value="距下次定点")
        self.unit_var = tk.StringVar(value="cup")
        self.amount_var = tk.StringVar(value="1")

        self._build_ui()
        self._apply_mode(self.MODE_COMPACT)
        self._refresh_display()
        self.scheduler.start()
        self._tick()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.root.title("喝水提醒")
        self.root.configure(bg=COLORS["bg"])
        self.root.attributes("-topmost", True)
        self.root.minsize(*COMPACT_MIN)

        self.compact_frame = tk.Frame(self.root, bg=COLORS["bg"])
        self.compact_frame.pack(fill=tk.BOTH, expand=True)
        self.compact_frame.grid_rowconfigure(1, weight=1)
        self.compact_frame.grid_columnconfigure(0, weight=1)

        header = tk.Frame(self.compact_frame, bg=COLORS["bg_soft"], height=32)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        tk.Label(
            header, text="💧 喝水提醒", font=("Microsoft YaHei UI", 10),
            bg=COLORS["bg_soft"], fg=COLORS["text_muted"], cursor="fleur",
        ).pack(side=tk.LEFT, padx=12, pady=6)
        settings_btn = tk.Label(
            header, text="⚙", font=("Microsoft YaHei UI", 14),
            bg=COLORS["bg_soft"], fg=COLORS["text_muted"], cursor="hand2",
        )
        chart_btn = tk.Label(
            header, text="📊", font=("Microsoft YaHei UI", 14),
            bg=COLORS["bg_soft"], fg=COLORS["text_muted"], cursor="hand2",
        )
        chart_btn.pack(side=tk.RIGHT, padx=(0, 8), pady=4)
        chart_btn.bind("<Button-1>", lambda _e: self._open_charts())
        settings_btn.pack(side=tk.RIGHT, padx=(0, 12), pady=4)
        settings_btn.bind("<Button-1>", lambda _e: self._open_settings())
        header.bind("<Button-1>", self._start_drag)
        header.bind("<B1-Motion>", self._on_drag)

        body = tk.Frame(self.compact_frame, bg=COLORS["bg"], padx=16, pady=12)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        info_row = tk.Frame(body, bg=COLORS["bg"])
        info_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        info_row.grid_columnconfigure(0, weight=1)

        left_info = tk.Frame(info_row, bg=COLORS["bg"])
        left_info.grid(row=0, column=0, sticky="w")
        tk.Label(
            left_info, textvariable=self.hint_var, font=FONT_COMPACT_INFO,
            bg=COLORS["bg"], fg=COLORS["text_muted"], anchor=tk.W,
        ).pack(anchor=tk.W)
        self.countdown_label = tk.Label(
            left_info, textvariable=self.countdown_var, font=FONT_COUNTDOWN,
            bg=COLORS["bg"], fg=COLORS["accent"], anchor=tk.W,
        )
        self.countdown_label.pack(anchor=tk.W, pady=(2, 0))
        tk.Label(
            left_info, textvariable=self.next_slot_var, font=FONT_COMPACT_INFO,
            bg=COLORS["bg"], fg=COLORS["text_muted"], anchor=tk.W,
        ).pack(anchor=tk.W, pady=(2, 0))

        right_info = tk.Frame(info_row, bg=COLORS["card"], padx=10, pady=8)
        right_info.grid(row=0, column=1, sticky="e", padx=(8, 0))
        tk.Label(right_info, text="今日", font=FONT_COMPACT_INFO, bg=COLORS["card"], fg=COLORS["text_muted"]).pack()
        tk.Label(
            right_info, textvariable=self.daily_var, font=("Microsoft YaHei UI", 11, "bold"),
            bg=COLORS["card"], fg=COLORS["text"],
        ).pack()

        btn_wrap = tk.Frame(body, bg=COLORS["accent_dark"], padx=2, pady=2)
        btn_wrap.grid(row=1, column=0, sticky="nsew")
        btn_wrap.grid_rowconfigure(0, weight=1)
        btn_wrap.grid_columnconfigure(0, weight=1)

        self.drink_btn = tk.Button(
            btn_wrap,
            text="🥤  喝了一杯",
            font=FONT_DRINK_BTN,
            bg=COLORS["accent_dark"],
            fg="white",
            activebackground=COLORS["accent"],
            activeforeground="white",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self._drink_one_cup,
        )
        self.drink_btn.grid(row=0, column=0, sticky="nsew", ipady=22)
        self.drink_btn.bind("<Enter>", lambda _e: self.drink_btn.configure(bg=COLORS["accent"]))
        self.drink_btn.bind("<Leave>", lambda _e: self._restore_drink_btn_color())

        self.expanded_frame = ttk.Frame(self.root, padding=16)

        hero = tk.Frame(self.expanded_frame, bg=COLORS["accent_soft"], height=56)
        hero.pack(fill=tk.X)
        hero.pack_propagate(False)
        self.reminder_title = tk.Label(
            hero, text="💧 该喝水啦！", font=FONT_BOLD, bg=COLORS["accent_soft"], fg=COLORS["accent"]
        )
        self.reminder_title.pack(expand=True)

        self.info_var = tk.StringVar()
        info_card = create_card(self.expanded_frame, "提醒信息", padding=12)
        info_card.pack(fill=tk.X, pady=(14, 10))
        ttk.Label(info_card, textvariable=self.info_var, style="Card.TLabel", justify=tk.LEFT).pack(anchor=tk.W)

        input_card = create_card(self.expanded_frame, "记录饮水", padding=12)
        input_card.pack(fill=tk.X, pady=(0, 12))

        row = ttk.Frame(input_card, style="Card.TFrame")
        row.pack(fill=tk.X)
        ttk.Label(row, text="数量", style="Card.TLabel", width=6).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.amount_var, width=10).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(row, text="杯", variable=self.unit_var, value="cup").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Radiobutton(row, text="ml", variable=self.unit_var, value="ml").pack(side=tk.LEFT)

        quick = ttk.Frame(input_card, style="Card.TFrame")
        quick.pack(fill=tk.X, pady=(10, 0))
        for cups in (0.5, 1, 2):
            ttk.Button(
                quick, text=f"{cups}杯", style="Ghost.TButton",
                command=lambda c=cups: self._quick_fill(c),
            ).pack(side=tk.LEFT, padx=(0, 6))

        btns = ttk.Frame(self.expanded_frame)
        btns.pack(fill=tk.X, pady=(4, 0))
        tk.Button(
            btns,
            text="提交并继续",
            font=FONT_DRINK_BTN,
            bg=COLORS["accent_dark"],
            fg="white",
            activebackground=COLORS["accent"],
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._submit_reminder,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=12)
        ttk.Button(btns, text="稍后", style="Ghost.TButton", command=self._skip_reminder).pack(
            side=tk.LEFT, ipadx=8, ipady=6
        )

    def _apply_mode(self, mode: str) -> None:
        self._mode = mode
        if mode == self.MODE_COMPACT:
            self.expanded_frame.pack_forget()
            self.compact_frame.pack(fill=tk.BOTH, expand=True)
            self.root.title("喝水提醒")
            self.root.resizable(True, True)
            self.root.minsize(*COMPACT_MIN)
            if self._saved_compact_geometry:
                self.root.geometry(self._saved_compact_geometry)
            elif not self._compact_initialized:
                self._place_window(*COMPACT_DEFAULT)
                self._compact_initialized = True
            self.root.attributes("-topmost", True)
        else:
            self._saved_compact_geometry = self.root.geometry()
            self.compact_frame.pack_forget()
            self.expanded_frame.pack(fill=tk.BOTH, expand=True)
            self.root.title("该喝水啦！")
            self.root.resizable(False, False)
            self._place_window(*EXPANDED_SIZE, center=True)
            self.root.attributes("-topmost", True)
            try:
                fade_in_window(self.root)
            except Exception:
                pass

    def _place_window(self, width: int, height: int, center: bool = False) -> None:
        self.root.update_idletasks()
        if center:
            x = (self.root.winfo_screenwidth() - width) // 2
            y = (self.root.winfo_screenheight() - height) // 3
        else:
            x = self.root.winfo_screenwidth() - width - 20
            y = self.root.winfo_screenheight() - height - 60
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _start_drag(self, event) -> None:
        if self._mode != self.MODE_COMPACT:
            return
        self._drag_offset = (event.x, event.y)

    def _on_drag(self, event) -> None:
        if self._mode != self.MODE_COMPACT:
            return
        x = self.root.winfo_x() + event.x - self._drag_offset[0]
        y = self.root.winfo_y() + event.y - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _refresh_display(self) -> None:
        total = self.store.daily_total_ml()
        goal = self.store.settings.daily_goal_ml
        self.daily_var.set(f"{total}\n/ {goal} ml")
        self.countdown_var.set(self.scheduler.format_countdown())
        next_time = self.scheduler.format_next_time()
        self.next_slot_var.set(f"下次 {next_time}")
        if self._mode == self.MODE_COMPACT:
            self.hint_var.set("距下次定点")

    def _tick(self) -> None:
        if self._mode == self.MODE_COMPACT:
            self.countdown_var.set(self.scheduler.format_countdown())
            self.next_slot_var.set(f"下次 {self.scheduler.format_next_time()}")
            total = self.store.daily_total_ml()
            goal = self.store.settings.daily_goal_ml
            self.daily_var.set(f"{total}\n/ {goal} ml")
        self.root.after(1000, self._tick)

    def _restore_drink_btn_color(self) -> None:
        if self.drink_btn.cget("text").startswith("✓"):
            return
        self.drink_btn.configure(bg=COLORS["accent_dark"])

    def _drink_one_cup(self) -> None:
        cup_ml = self.store.settings.cup_ml
        self.store.add_record(amount_ml=cup_ml, unit="cup", raw_amount=1.0)
        self._refresh_display()
        self._flash_drink_button()
        if self._settings_window and self._settings_window.winfo_exists():
            self._settings_window.refresh()

    def _flash_drink_button(self) -> None:
        self.drink_btn.configure(bg=COLORS["success"], text="✓  已记录！", font=FONT_DRINK_FLASH)
        self.root.after(1200, lambda: self.drink_btn.configure(
            bg=COLORS["accent_dark"], text="🥤  喝了一杯", font=FONT_DRINK_BTN
        ))

    def _on_timer_due(self, now: datetime, next_at: datetime) -> None:
        self._pending_next_slot = next_at
        daily = self.store.daily_total_ml()
        self.info_var.set(
            f"当前时间  {now.strftime('%H:%M:%S')}\n"
            f"今日已喝  {daily} ml\n"
            f"下次定点  {next_at.strftime('%H:%M')}\n"
            f"（定点提醒，与是否点击喝水无关）"
        )
        self.amount_var.set("1")
        self.unit_var.set("cup")
        self._apply_mode(self.MODE_REMINDER)
        self._pulse_reminder()

    def _pulse_reminder(self) -> None:
        if self._mode != self.MODE_REMINDER or not self.root.winfo_exists():
            return
        colors = [COLORS["accent"], COLORS["warning"], COLORS["success"]]
        self.reminder_title.configure(fg=colors[int(datetime.now().timestamp() * 2) % 3])
        self.root.after(500, self._pulse_reminder)

    def _quick_fill(self, cups: float) -> None:
        self.unit_var.set("cup")
        self.amount_var.set(str(cups))

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

    def _submit_reminder(self) -> None:
        try:
            amount_ml, unit, raw_amount = self._parse_amount()
        except ValueError as exc:
            messagebox.showwarning("输入有误", str(exc), parent=self.root)
            return
        self.store.add_record(amount_ml=amount_ml, unit=unit, raw_amount=raw_amount)
        self._finish_reminder()

    def _skip_reminder(self) -> None:
        self._finish_reminder()

    def _finish_reminder(self) -> None:
        self.scheduler.continue_to_next(self._pending_next_slot)
        self._pending_next_slot = None
        self._apply_mode(self.MODE_COMPACT)
        self._refresh_display()
        if self._settings_window and self._settings_window.winfo_exists():
            self._settings_window.refresh()

    def _open_settings(self) -> None:
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.refresh()
            return

        def _on_saved() -> None:
            self.scheduler.reschedule()
            self._refresh_display()

        self._settings_window = SettingsWindow(self.root, self.store, _on_saved)

    def _open_charts(self) -> None:
        if self._chart_window is not None and self._chart_window.winfo_exists():
            self._chart_window.lift()
            self._chart_window.period_var.set("day")
            self._chart_window._render_chart()
            return
        self._chart_window = ChartWindow(self.root, self.store)

    def _on_close(self) -> None:
        if self._mode == self.MODE_REMINDER:
            if messagebox.askyesno("确认", "提醒尚未处理，确定关闭吗？", parent=self.root):
                self.scheduler.stop()
                self.root.destroy()
            return
        self.scheduler.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    import socket
    import sys

    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", 52731))
        lock.listen(1)
    except OSError:
        sys.exit(0)

    app = WaterReminderApp()
    app._instance_lock = lock  # 保持端口占用，防止重复启动
    app.run()


if __name__ == "__main__":
    main()
