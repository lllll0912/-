"""访问密码保护（公网部署时设置 BILL_ACCESS_PASSWORD）。"""

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


def access_password() -> str:
    return (os.environ.get("BILL_ACCESS_PASSWORD") or "").strip()


def auth_enabled() -> bool:
    return bool(access_password())


def is_logged_in() -> bool:
    if not auth_enabled():
        return True
    return bool(session.get("bill_auth_ok"))


def home_url() -> str:
    return url_for("import_page")


def safe_next(raw: str | None) -> str:
    """只允许站内相对路径，防止开放重定向。"""
    nxt = (raw or "").strip()
    if nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return home_url()


def _password_ok(pwd: str, expected: str) -> bool:
    a = hashlib.sha256(pwd.encode("utf-8")).digest()
    b = hashlib.sha256(expected.encode("utf-8")).digest()
    return secrets.compare_digest(a, b)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if not auth_enabled():
        return redirect(home_url())
    if is_logged_in():
        return redirect(safe_next(request.args.get("next")))

    error = ""
    if request.method == "POST":
        pwd = (request.form.get("password") or "").strip()
        if _password_ok(pwd, access_password()):
            session["bill_auth_ok"] = True
            session.permanent = True
            return redirect(safe_next(request.form.get("next") or request.args.get("next")))
        error = "密码错误"
    # 登录页隐藏域用原始 next，避免无 next 时反复变成首页路径干扰
    nxt = (request.args.get("next") or request.form.get("next") or "").strip()
    if not (nxt.startswith("/") and not nxt.startswith("//")):
        nxt = ""
    return render_template("login.html", error=error, next=nxt)


@auth_bp.route("/logout")
def logout():
    session.pop("bill_auth_ok", None)
    flash("已退出登录", "success")
    if auth_enabled():
        return redirect(url_for("auth.login"))
    return redirect(home_url())


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped
