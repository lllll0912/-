"""笔记专栏：SQLite + 图片资源。"""

from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ALLOWED_IMAGE_EXT = frozenset({"jpg", "jpeg", "png", "gif", "webp"})
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _site_root() -> Path:
    return Path(__file__).resolve().parents[2]


def notes_db_path() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / "notes.db"
    return _site_root() / "data" / "notes.db"


def notes_assets_root() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / "notes_assets"
    return _site_root() / "data" / "notes_assets"


@contextmanager
def _cursor():
    path = notes_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_notes_db() -> None:
    with _cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content_md TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def list_notes() -> list[dict[str, Any]]:
    init_notes_db()
    with _cursor() as cur:
        cur.execute(
            "SELECT id, title, content_md, created_at, updated_at FROM notes ORDER BY updated_at DESC, id DESC"
        )
        return [dict(r) for r in cur.fetchall()]


def get_note(note_id: int) -> Optional[dict[str, Any]]:
    init_notes_db()
    with _cursor() as cur:
        cur.execute(
            "SELECT id, title, content_md, created_at, updated_at FROM notes WHERE id = ?",
            (note_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def create_note(title: str, content_md: str = "") -> int:
    init_notes_db()
    ts = _now()
    title = (title or "").strip() or "未命名笔记"
    with _cursor() as cur:
        cur.execute(
            "INSERT INTO notes (title, content_md, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, content_md or "", ts, ts),
        )
        return int(cur.lastrowid)


def update_note(note_id: int, title: str, content_md: str) -> bool:
    init_notes_db()
    title = (title or "").strip() or "未命名笔记"
    with _cursor() as cur:
        cur.execute(
            "UPDATE notes SET title = ?, content_md = ?, updated_at = ? WHERE id = ?",
            (title, content_md or "", _now(), note_id),
        )
        return cur.rowcount > 0


def delete_note(note_id: int) -> bool:
    init_notes_db()
    with _cursor() as cur:
        cur.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        ok = cur.rowcount > 0
    # 尽量清理图片目录
    asset_dir = notes_assets_root() / str(note_id)
    if asset_dir.exists():
        for f in asset_dir.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
        try:
            asset_dir.rmdir()
        except OSError:
            pass
    return ok


def save_note_image(note_id: int, filename: str, data: bytes) -> str:
    """保存图片，返回可嵌入 Markdown 的站内 URL 路径。"""
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("图片不能超过 5MB")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError("仅支持 jpg/png/gif/webp")
    # 简单头校验
    if not data:
        raise ValueError("空文件")

    note_dir = notes_assets_root() / str(note_id)
    note_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{stamp}_{secrets.token_hex(4)}.{ext}"
    path = note_dir / name
    path.write_bytes(data)
    return f"/notes/assets/{note_id}/{name}"


def resolve_asset(note_id: int, filename: str) -> Optional[Path]:
    if not re.fullmatch(r"[0-9]{8}_[0-9]{6}_[0-9a-f]{8}\.(jpg|jpeg|png|gif|webp)", filename, re.I):
        return None
    path = notes_assets_root() / str(note_id) / filename
    if not path.is_file():
        return None
    # 防穿越
    try:
        path.resolve().relative_to(notes_assets_root().resolve())
    except ValueError:
        return None
    return path


DEFAULT_MD_HINTS: list[dict[str, str]] = [
    {"title": "一级标题", "md": "# 标题", "note": "行首一个 # 加空格"},
    {"title": "二级标题", "md": "## 标题", "note": ""},
    {"title": "三级标题", "md": "### 标题", "note": ""},
    {"title": "加粗", "md": "**加粗文字**", "note": ""},
    {"title": "斜体", "md": "*斜体文字*", "note": ""},
    {"title": "项目符号", "md": "- 条目一\n- 条目二", "note": ""},
    {"title": "有序号", "md": "1. 第一条\n2. 第二条", "note": ""},
    {"title": "引用", "md": "> 引用内容", "note": ""},
    {"title": "链接", "md": "[显示文字](https://)", "note": ""},
    {"title": "图片", "md": "![说明](图片地址)", "note": "也可用工具栏上传"},
    {"title": "分割线", "md": "---", "note": ""},
    {"title": "行内代码", "md": "`代码`", "note": ""},
]


def md_hints_path() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / "notes_md_hints.json"
    return _site_root() / "data" / "notes_md_hints.json"


def load_md_hints() -> list[dict[str, str]]:
    path = md_hints_path()
    if not path.is_file():
        return [dict(x) for x in DEFAULT_MD_HINTS]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return [dict(x) for x in DEFAULT_MD_HINTS]
        out = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            md = str(item.get("md") or "")
            if not title and not md:
                continue
            out.append(
                {
                    "title": title or "未命名",
                    "md": md,
                    "note": str(item.get("note") or "").strip(),
                }
            )
        return out or [dict(x) for x in DEFAULT_MD_HINTS]
    except Exception:
        return [dict(x) for x in DEFAULT_MD_HINTS]


def save_md_hints(items: list[dict[str, str]]) -> list[dict[str, str]]:
    cleaned = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        md = str(item.get("md") or "")
        if not title and not md.strip():
            continue
        cleaned.append(
            {
                "title": title or "未命名",
                "md": md,
                "note": str(item.get("note") or "").strip(),
            }
        )
    if not cleaned:
        cleaned = [dict(x) for x in DEFAULT_MD_HINTS]
    path = md_hints_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    return cleaned
