"""饮水统计图表窗口。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from data_store import DataStore
from theme import COLORS, create_card, fade_in_window, setup_theme


class ChartWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc, store: DataStore) -> None:
        super().__init__(parent)
        self.store = store
        self.title("饮水统计")
        self.geometry("920x580")
        self.minsize(780, 500)
        self.configure(bg=COLORS["bg"])
        setup_theme(self)

        self.period_var = tk.StringVar(value="day")
        self.chart_type_var = tk.StringVar(value="bar")

        self._build_controls()
        self._build_chart_area()
        self._render_chart()
        fade_in_window(self)

    def _build_controls(self) -> None:
        toolbar = create_card(self, "统计选项", padding=14)
        toolbar.pack(fill=tk.X, padx=16, pady=(16, 8))

        row1 = ttk.Frame(toolbar, style="Card.TFrame")
        row1.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(row1, text="统计周期", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        for text, value in [("每日", "day"), ("每周日均", "week"), ("每月日均", "month")]:
            ttk.Radiobutton(
                row1, text=text, variable=self.period_var, value=value, command=self._render_chart
            ).pack(side=tk.LEFT, padx=(0, 10))

        row2 = ttk.Frame(toolbar, style="Card.TFrame")
        row2.pack(fill=tk.X)
        ttk.Label(row2, text="图表类型", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(
            row2, text="柱状图", variable=self.chart_type_var, value="bar", command=self._render_chart
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(
            row2, text="折线图", variable=self.chart_type_var, value="line", command=self._render_chart
        ).pack(side=tk.LEFT)

        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var, style="Muted.TLabel", padding=(20, 0)).pack(anchor=tk.W)

    def _build_chart_area(self) -> None:
        self.chart_frame = create_card(self, "数据可视化", padding=12)
        self.chart_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        self.canvas: FigureCanvasTkAgg | None = None

    def _render_chart(self) -> None:
        period = self.period_var.get()
        chart_type = self.chart_type_var.get()
        data = self.store.average_by_period(period)

        for child in self.chart_frame.winfo_children():
            child.destroy()

        if not data:
            ttk.Label(
                self.chart_frame,
                text="暂无饮水记录，先记录几次喝水后再来看统计吧。",
                style="CardMuted.TLabel",
            ).pack(expand=True)
            self.summary_var.set("")
            return

        labels = [item["label"] for item in data]
        values = [item["total_ml"] for item in data]

        period_names = {"day": "每日", "week": "每周日均", "month": "每月日均"}
        y_label = "饮水量 (ml)" if period == "day" else "日均饮水量 (ml)"
        title = f"{period_names[period]}饮水统计"

        fig = Figure(figsize=(8.6, 4.6), dpi=100, facecolor=COLORS["card"])
        ax = fig.add_subplot(111, facecolor=COLORS["input_bg"])
        color = COLORS["accent"]
        grid_color = COLORS["border"]
        text_color = COLORS["text_muted"]

        if chart_type == "line":
            ax.plot(labels, values, marker="o", linewidth=2.5, color=color, markerfacecolor=COLORS["success"])
            ax.fill_between(range(len(values)), values, alpha=0.12, color=color)
        else:
            bars = ax.bar(labels, values, color=color, alpha=0.88, edgecolor=COLORS["accent_dark"], linewidth=0.6)
            for bar, value in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    value,
                    f"{value}",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    color=text_color,
                )

        ax.set_title(title, fontsize=13, pad=12, color=COLORS["text"])
        ax.set_ylabel(y_label, color=text_color)
        ax.tick_params(colors=text_color)
        ax.grid(axis="y", linestyle="--", alpha=0.35, color=grid_color)
        for spine in ax.spines.values():
            spine.set_color(grid_color)
        fig.autofmt_xdate(rotation=28, ha="right")

        if chart_type == "line":
            for idx, value in enumerate(values):
                ax.text(idx, value, f"{value}", ha="center", va="bottom", fontsize=9, color=text_color)

        fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        avg_value = int(round(sum(values) / len(values)))
        self.summary_var.set(
            f"共 {len(values)} 个统计点，平均 {avg_value} ml"
            + ("（周/月为周期内日均）" if period != "day" else "")
        )
