"""访问控制：所有者（密码）/ 游客（只读诗词与笔记）。"""

from __future__ import annotations

import hashlib
import os
import secrets
from functools import wraps

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

auth_bp = Blueprint("auth", __name__)

ROLE_OWNER = "owner"
ROLE_GUEST = "guest"

# 游客允许的 endpoint（只读）
GUEST_ALLOWED_ENDPOINTS = frozenset(
    {
        "auth.login",
        "auth.logout",
        "auth.enter_guest",
        "static",
        "poems_page",
        "notes.notes_list",
        "notes.notes_view",
        "notes.notes_asset",
    }
)


def access_password() -> str:
    return (os.environ.get("BILL_ACCESS_PASSWORD") or "").strip()


def auth_enabled() -> bool:
    return bool(access_password())


def access_role() -> str | None:
    role = session.get("access_role")
    if role in (ROLE_OWNER, ROLE_GUEST):
        return role
    # 兼容旧 session
    if session.get("bill_auth_ok"):
        return ROLE_OWNER
    return None


def is_owner() -> bool:
    role = access_role()
    if not auth_enabled():
        return role != ROLE_GUEST
    return role == ROLE_OWNER


def is_guest() -> bool:
    return access_role() == ROLE_GUEST


def has_site_access() -> bool:
    """已选择所有者或游客。"""
    return access_role() in (ROLE_OWNER, ROLE_GUEST)


def is_logged_in() -> bool:
    """兼容旧模板：表示「所有者」。"""
    if not auth_enabled():
        return not is_guest()
    return is_owner()


def home_url() -> str:
    if is_guest():
        return url_for("poems_page")
    return url_for("import_page")


def safe_next(raw: str | None) -> str:
    nxt = (raw or "").strip()
    if nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return home_url()


def _password_ok(pwd: str, expected: str) -> bool:
    a = hashlib.sha256(pwd.encode("utf-8")).digest()
    b = hashlib.sha256(expected.encode("utf-8")).digest()
    return secrets.compare_digest(a, b)


def guest_can_access(endpoint: str | None) -> bool:
    if not endpoint:
        return False
    if endpoint in GUEST_ALLOWED_ENDPOINTS:
        return True
    return False


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    nxt = (request.args.get("next") or request.form.get("next") or "").strip()
    if not (nxt.startswith("/") and not nxt.startswith("//")):
        nxt = ""

    if request.method == "POST":
        mode = (request.form.get("mode") or "owner").strip()
        if mode == "guest":
            session.clear()
            session["access_role"] = ROLE_GUEST
            session.permanent = True
            flash("已进入游客模式（仅可查看诗词与笔记）", "success")
            return redirect(url_for("poems_page"))

        # owner
        if not auth_enabled():
            session.clear()
            session["access_role"] = ROLE_OWNER
            session.permanent = True
            return redirect(safe_next(nxt) if nxt else url_for("import_page"))

        pwd = (request.form.get("password") or "").strip()
        if _password_ok(pwd, access_password()):
            session.clear()
            session["access_role"] = ROLE_OWNER
            session["bill_auth_ok"] = True
            session.permanent = True
            return redirect(safe_next(nxt) if nxt else url_for("import_page"))
        error = "密码错误"
        return render_template(
            "login.html",
            error=error,
            next=nxt,
            auth_enabled=auth_enabled(),
        )

    # GET：已选角色则进首页；要切换请先「退出 / 切换模式」
    if access_role() == ROLE_OWNER:
        return redirect(safe_next(nxt) if nxt else url_for("import_page"))
    if access_role() == ROLE_GUEST:
        return redirect(url_for("poems_page"))

    return render_template(
        "login.html",
        error=error,
        next=nxt,
        auth_enabled=auth_enabled(),
    )


@auth_bp.route("/guest", methods=["POST"])
def enter_guest():
    session.clear()
    session["access_role"] = ROLE_GUEST
    session.permanent = True
    flash("已进入游客模式（仅可查看诗词与笔记）", "success")
    return redirect(url_for("poems_page"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("已退出", "success")
    return redirect(url_for("auth.login"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_owner():
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def owner_required(view):
    return login_required(view)
