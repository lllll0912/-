"""站点所有者密码（网页可改，环境变量优先）。"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from share_profiles import hash_password


def _meta_dir() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        root = Path(data_dir) / "_meta"
    else:
        root = Path(__file__).resolve().parent / "数据" / "_meta"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _auth_path() -> Path:
    return _meta_dir() / "site_auth.json"


def _env_path() -> Path:
    return Path(__file__).resolve().parent / ".env"


def env_password() -> str:
    return (os.environ.get("BILL_ACCESS_PASSWORD") or "").strip()


def password_managed_by_env() -> bool:
    return bool(env_password())


def _load_raw() -> dict[str, Any]:
    path = _auth_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def file_password_hash() -> str:
    return str(_load_raw().get("owner_password_hash") or "").strip()


def auth_configured() -> bool:
    return bool(env_password() or file_password_hash())


def verify_owner_password(pwd: str) -> bool:
    digest = hash_password(pwd)
    plain_env = env_password()
    if plain_env and secrets.compare_digest(digest, hash_password(plain_env)):
        return True
    file_digest = file_password_hash()
    if file_digest and secrets.compare_digest(digest, file_digest):
        return True
    if not plain_env and not file_digest:
        return True
    return False


def set_owner_password(current_pwd: str, new_pwd: str) -> None:
    new_plain = (new_pwd or "").strip()
    if len(new_plain) < 6:
        raise ValueError("新密码至少 6 位")
    if auth_configured() and not verify_owner_password(current_pwd):
        raise ValueError("当前密码不正确")

    payload = _load_raw()
    payload["owner_password_hash"] = hash_password(new_plain)
    _auth_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if password_managed_by_env():
        _update_env_password(new_plain)


def sync_env_password_hash() -> None:
    """将环境变量中的密码同步到本地 hash 文件（便于网页改密）。"""
    plain = env_password()
    if not plain:
        return
    payload = _load_raw()
    payload["owner_password_hash"] = hash_password(plain)
    _auth_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bootstrap_owner_password(plain: str) -> None:
    """初始化密码（仅当尚未配置时）。"""
    if auth_configured():
        return
    plain = (plain or "").strip()
    if not plain:
        return
    payload = _load_raw()
    payload["owner_password_hash"] = hash_password(plain)
    _auth_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_env_if_missing(plain)


def _write_env_if_missing(plain: str) -> None:
    env_path = _env_path()
    if env_path.is_file():
        return
    secret = os.environ.get("BILL_SECRET_KEY") or secrets.token_hex(24)
    content = (
        "# 自动生成，勿提交 Git\n"
        f"BILL_ACCESS_PASSWORD={plain}\n"
        f"BILL_SECRET_KEY={secret}\n"
        "BILL_COOKIE_SECURE=0\n"
    )
    env_path.write_text(content, encoding="utf-8")


def _update_env_password(plain: str) -> None:
    env_path = _env_path()
    lines: list[str] = []
    found = False
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            if raw.strip().startswith("BILL_ACCESS_PASSWORD="):
                lines.append(f"BILL_ACCESS_PASSWORD={plain}")
                found = True
            else:
                lines.append(raw)
    if not found:
        lines.append(f"BILL_ACCESS_PASSWORD={plain}")
    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.environ["BILL_ACCESS_PASSWORD"] = plain
