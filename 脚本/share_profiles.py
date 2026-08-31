"""分享访问配置：按人分配可浏览的站点模块。"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

SITE_MODULES: dict[str, dict[str, str]] = {
    "collection": {"label": "作品 / 人物", "home": "collection.collection_home"},
    "health": {"label": "医疗日历", "home": "health.health_calendar"},
    "poems": {"label": "每日诗词", "home": "poems_page"},
    "notes": {"label": "笔记专栏", "home": "notes.notes_list"},
    "bills": {"label": "账单财务", "home": "import_page"},
    "water": {"label": "喝水提醒", "home": "water.water_home"},
    "journal": {"label": "生活日志", "home": "journal_page"},
}


def _profiles_path() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        root = Path(data_dir) / "_meta"
    else:
        root = Path(__file__).resolve().parent / "数据" / "_meta"
    root.mkdir(parents=True, exist_ok=True)
    return root / "share_profiles.json"


def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()


def _load_raw() -> dict[str, Any]:
    path = _profiles_path()
    if not path.is_file():
        return {"profiles": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"profiles": []}
    if not isinstance(data, dict):
        return {"profiles": []}
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        profiles = []
    return {"profiles": profiles}


def _save_raw(data: dict[str, Any]) -> None:
    path = _profiles_path()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_modules(modules: list[str] | None) -> list[str]:
    out: list[str] = []
    for m in modules or []:
        key = (m or "").strip()
        if key in SITE_MODULES and key not in out:
            out.append(key)
    return out


def list_profiles_public() -> list[dict[str, Any]]:
    """列表展示（不含 password_hash）。"""
    rows = []
    for p in _load_raw().get("profiles", []):
        if not isinstance(p, dict):
            continue
        rows.append(
            {
                "id": p.get("id") or "",
                "name": p.get("name") or "",
                "modules": _normalize_modules(p.get("modules")),
                "token": p.get("token") or "",
                "created_at": p.get("created_at") or "",
            }
        )
    return rows


def find_profile_by_password(pwd: str) -> dict[str, Any] | None:
    digest = hash_password((pwd or "").strip())
    for p in _load_raw().get("profiles", []):
        if not isinstance(p, dict):
            continue
        if secrets.compare_digest(str(p.get("password_hash") or ""), digest):
            return p
    return None


def find_profile_by_token(token: str) -> dict[str, Any] | None:
    tok = (token or "").strip()
    if not tok:
        return None
    for p in _load_raw().get("profiles", []):
        if not isinstance(p, dict):
            continue
        if secrets.compare_digest(str(p.get("token") or ""), tok):
            return p
    return None


def find_profile_by_id(profile_id: str) -> dict[str, Any] | None:
    pid = (profile_id or "").strip()
    for p in _load_raw().get("profiles", []):
        if isinstance(p, dict) and str(p.get("id") or "") == pid:
            return p
    return None


def create_profile(name: str, password: str | None, modules: list[str]) -> tuple[dict[str, Any], str]:
    label = (name or "").strip()
    if not label:
        raise ValueError("请填写分享对象名称")
    mods = _normalize_modules(modules)
    if not mods:
        raise ValueError("请至少选择一个可访问模块")

    plain = (password or "").strip() or secrets.token_urlsafe(8)
    profile = {
        "id": "p_" + secrets.token_hex(6),
        "name": label,
        "password_hash": hash_password(plain),
        "token": secrets.token_urlsafe(24),
        "modules": mods,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    data = _load_raw()
    profiles = data.setdefault("profiles", [])
    profiles.append(profile)
    _save_raw(data)
    public = {
        "id": profile["id"],
        "name": profile["name"],
        "modules": profile["modules"],
        "token": profile["token"],
        "created_at": profile["created_at"],
    }
    return public, plain


def delete_profile(profile_id: str) -> bool:
    pid = (profile_id or "").strip()
    data = _load_raw()
    profiles = data.get("profiles", [])
    kept = [p for p in profiles if isinstance(p, dict) and str(p.get("id") or "") != pid]
    if len(kept) == len(profiles):
        return False
    data["profiles"] = kept
    _save_raw(data)
    return True


def update_profile(profile_id: str, name: str, modules: list[str]) -> bool:
    pid = (profile_id or "").strip()
    label = (name or "").strip()
    if not label:
        raise ValueError("请填写分享对象名称")
    mods = _normalize_modules(modules)
    if not mods:
        raise ValueError("请至少选择一个可访问模块")
    data = _load_raw()
    found = False
    for p in data.get("profiles", []):
        if not isinstance(p, dict) or str(p.get("id") or "") != pid:
            continue
        p["name"] = label
        p["modules"] = mods
        found = True
        break
    if not found:
        return False
    _save_raw(data)
    return True


def reset_profile_password(profile_id: str) -> tuple[str, str] | None:
    """重置分享密码，返回 (profile_id, plain_password)。"""
    pid = (profile_id or "").strip()
    plain = secrets.token_urlsafe(8)
    data = _load_raw()
    for p in data.get("profiles", []):
        if isinstance(p, dict) and str(p.get("id") or "") == pid:
            p["password_hash"] = hash_password(plain)
            _save_raw(data)
            return pid, plain
    return None


def regenerate_profile_token(profile_id: str) -> str | None:
    pid = (profile_id or "").strip()
    token = secrets.token_urlsafe(24)
    data = _load_raw()
    for p in data.get("profiles", []):
        if isinstance(p, dict) and str(p.get("id") or "") == pid:
            p["token"] = token
            _save_raw(data)
            return token
    return None


def profile_session_payload(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "share_profile_id": str(profile.get("id") or ""),
        "share_profile_name": str(profile.get("name") or ""),
        "share_modules": _normalize_modules(profile.get("modules")),
    }
