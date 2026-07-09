"""生成并应用应用图标。"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ICON_PATH = ASSETS_DIR / "water.ico"


def ensure_icon() -> Path:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    if not ICON_PATH.exists():
        _generate_icon()
    return ICON_PATH


def _draw_drop(size: int):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(2, size // 12)
    draw.ellipse(
        (pad, pad, size - pad, size - pad),
        fill=(11, 95, 165, 255),
        outline=(56, 189, 248, 255),
        width=max(1, size // 32),
    )

    cx = size // 2
    top = int(size * 0.22)
    mid_y = int(size * 0.46)
    bottom = int(size * 0.76)
    half_w = int(size * 0.18)

    drop_color = (224, 242, 254, 245)
    highlight = (255, 255, 255, 180)

    draw.polygon([(cx, top), (cx - half_w, mid_y), (cx + half_w, mid_y)], fill=drop_color)
    draw.ellipse(
        (cx - half_w, mid_y - half_w // 2, cx + half_w, mid_y + half_w),
        fill=drop_color,
    )
    draw.ellipse(
        (cx - half_w // 3, top + half_w // 2, cx - half_w // 6, top + half_w),
        fill=highlight,
    )

    cup_y = int(size * 0.8)
    draw.rounded_rectangle(
        (cx - half_w, cup_y - 2, cx + half_w, cup_y + max(2, size // 16)),
        radius=max(1, size // 24),
        fill=(125, 211, 252, 220),
    )
    return img


def _generate_icon() -> None:
    from PIL import Image

    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [_draw_drop(s) for s in sizes]
    images[-1].save(
        ICON_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )


def apply_window_icon(window: tk.Misc) -> None:
    path = ensure_icon()
    try:
        window.iconbitmap(default=str(path))
    except tk.TclError:
        pass

    try:
        from PIL import Image, ImageTk

        photo = ImageTk.PhotoImage(Image.open(path).resize((32, 32), Image.Resampling.LANCZOS))
        window.iconphoto(True, photo)
        window._water_icon_photo = photo  # type: ignore[attr-defined]
    except Exception:
        pass
