"""应用视觉主题与交互组件。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

# 深海蓝 + 水光青 主题
COLORS = {
    "bg": "#0b1220",
    "bg_soft": "#111b2e",
    "card": "#162033",
    "card_hover": "#1c2a42",
    "border": "#2a3a55",
    "text": "#e8eef8",
    "text_muted": "#8fa3bf",
    "accent": "#38bdf8",
    "accent_dark": "#0ea5e9",
    "accent_soft": "#1d4f6b",
    "success": "#34d399",
    "warning": "#fbbf24",
    "danger": "#f87171",
    "input_bg": "#0f1a2c",
    "shadow": "#060a12",
}

FONT_FAMILY = "Microsoft YaHei UI"
FONT_TITLE = (FONT_FAMILY, 22, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 10)
FONT_BODY = (FONT_FAMILY, 10)
FONT_BOLD = (FONT_FAMILY, 11, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_HERO = (FONT_FAMILY, 28, "bold")


def setup_theme(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.configure(bg=COLORS["bg"])

    style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], font=FONT_BODY)
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Card.TFrame", background=COLORS["card"])
    style.configure("Soft.TFrame", background=COLORS["bg_soft"])

    style.configure(
        "Card.TLabelframe",
        background=COLORS["card"],
        foreground=COLORS["accent"],
        bordercolor=COLORS["border"],
        relief="flat",
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=COLORS["card"],
        foreground=COLORS["accent"],
        font=FONT_BOLD,
    )

    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Card.TLabel", background=COLORS["card"], foreground=COLORS["text"])
    style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["text_muted"], font=FONT_SMALL)
    style.configure("CardMuted.TLabel", background=COLORS["card"], foreground=COLORS["text_muted"], font=FONT_SMALL)
    style.configure("Hero.TLabel", background=COLORS["bg_soft"], foreground=COLORS["text"], font=FONT_HERO)
    style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONT_TITLE)
    style.configure("Accent.TLabel", background=COLORS["bg"], foreground=COLORS["accent"], font=FONT_BOLD)
    style.configure("CardAccent.TLabel", background=COLORS["card"], foreground=COLORS["accent"], font=FONT_BOLD)

    style.configure(
        "TEntry",
        fieldbackground=COLORS["input_bg"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        insertcolor=COLORS["accent"],
        padding=6,
    )
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["input_bg"],
        background=COLORS["card"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        arrowcolor=COLORS["accent"],
        padding=4,
    )
    style.map("TCombobox", fieldbackground=[("readonly", COLORS["input_bg"])])

    style.configure(
        "TCheckbutton",
        background=COLORS["card"],
        foreground=COLORS["text"],
    )
    style.map("TCheckbutton", background=[("active", COLORS["card"])])

    style.configure(
        "TRadiobutton",
        background=COLORS["card"],
        foreground=COLORS["text"],
    )
    style.map("TRadiobutton", background=[("active", COLORS["card"])])

    _configure_button(style, "TButton", COLORS["card"], COLORS["text"], COLORS["card_hover"])
    _configure_button(style, "Accent.TButton", COLORS["accent_dark"], "#041018", COLORS["accent"])
    _configure_button(style, "Ghost.TButton", COLORS["card"], COLORS["text_muted"], COLORS["card_hover"])
    _configure_button(style, "Danger.TButton", "#7f1d1d", "#fee2e2", "#b91c1c")

    style.configure(
        "Treeview",
        background=COLORS["input_bg"],
        foreground=COLORS["text"],
        fieldbackground=COLORS["input_bg"],
        bordercolor=COLORS["border"],
        rowheight=30,
        font=FONT_BODY,
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["card"],
        foreground=COLORS["accent"],
        font=FONT_BOLD,
        relief="flat",
    )
    style.map("Treeview", background=[("selected", COLORS["accent_soft"])], foreground=[("selected", COLORS["text"])])

    return style


def _configure_button(style: ttk.Style, name: str, bg: str, fg: str, active_bg: str) -> None:
    style.configure(name, background=bg, foreground=fg, borderwidth=0, padding=(14, 8), font=FONT_BOLD)
    style.map(name, background=[("active", active_bg), ("pressed", active_bg)])


def create_card(parent: tk.Misc, title: str | None = None, padding: int = 16) -> ttk.Frame:
    if title:
        frame = ttk.LabelFrame(parent, text=f"  {title}  ", style="Card.TLabelframe", padding=padding)
    else:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=padding)
    return frame


class WaterProgressRing(tk.Canvas):
    """动态水环进度：展示今日饮水占目标比例。"""

    def __init__(
        self,
        parent: tk.Misc,
        size: int = 160,
        goal_ml: int = 2000,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=COLORS["bg_soft"],
            highlightthickness=0,
            **kwargs,
        )
        self.size = size
        self.goal_ml = max(1, goal_ml)
        self.current_ml = 0
        self._display_progress = 0.0
        self._target_progress = 0.0
        self._pulse = 0
        self._animating = False

    def set_values(self, current_ml: int, goal_ml: int | None = None) -> None:
        if goal_ml is not None:
            self.goal_ml = max(1, goal_ml)
        self.current_ml = max(0, current_ml)
        self._target_progress = min(1.0, self.current_ml / self.goal_ml)
        if not self._animating:
            self._animating = True
            self._animate()

    def _animate(self) -> None:
        diff = self._target_progress - self._display_progress
        if abs(diff) > 0.005:
            self._display_progress += diff * 0.18
        else:
            self._display_progress = self._target_progress

        self._pulse = (self._pulse + 8) % 360
        self._draw()

        if abs(self._target_progress - self._display_progress) > 0.005:
            self.after(30, self._animate)
        else:
            self._animating = False

    def _draw(self) -> None:
        self.delete("all")
        pad = 14
        x0, y0, x1, y1 = pad, pad, self.size - pad, self.size - pad

        self.create_oval(x0, y0, x1, y1, outline=COLORS["border"], width=10)

        extent = max(0.0, self._display_progress * 360)
        if extent > 0:
            pulse_color = COLORS["accent"] if self._pulse < 180 else COLORS["accent_dark"]
            self.create_arc(
                x0,
                y0,
                x1,
                y1,
                start=90,
                extent=-extent,
                outline=pulse_color,
                width=10,
                style="arc",
            )

        cx, cy = self.size / 2, self.size / 2
        self.create_text(cx, cy - 14, text=f"{self.current_ml}", fill=COLORS["text"], font=FONT_HERO)
        self.create_text(cx, cy + 18, text="ml 今日", fill=COLORS["text_muted"], font=FONT_SMALL)
        pct = int(round(self._display_progress * 100))
        self.create_text(cx, cy + 36, text=f"{pct}% / 目标 {self.goal_ml}", fill=COLORS["accent"], font=FONT_SMALL)


def bind_hover(widget: tk.Widget, on_enter: Callable | None = None, on_leave: Callable | None = None) -> None:
    def _enter(_event) -> None:
        if on_enter:
            on_enter()

    def _leave(_event) -> None:
        if on_leave:
            on_leave()

    widget.bind("<Enter>", _enter)
    widget.bind("<Leave>", _leave)


def fade_in_window(window: tk.Toplevel, duration_ms: int = 220, steps: int = 11) -> None:
    try:
        window.attributes("-alpha", 0.0)
    except tk.TclError:
        return

    step = 0

    def _tick() -> None:
        nonlocal step
        step += 1
        alpha = min(1.0, step / steps)
        try:
            window.attributes("-alpha", alpha)
        except tk.TclError:
            return
        if step < steps:
            window.after(duration_ms // steps, _tick)

    _tick()
