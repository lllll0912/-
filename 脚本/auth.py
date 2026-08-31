"""访问控制：所有者 / 游客 / 分享访问（按模块）。"""

from __future__ import annotations

import hashlib
import os
import secrets
from functools import wraps

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from share_profiles import (
    SITE_MODULES,
    create_profile,
    delete_profile,
    find_profile_by_password,
    find_profile_by_token,
    list_profiles_public,
    profile_session_payload,
    regenerate_profile_token,
    reset_profile_password,
    update_profile,
)
from site_auth import (
    auth_configured,
    password_managed_by_env,
    set_owner_password,
    verify_owner_password,
)

auth_bp = Blueprint("auth", __name__)

ROLE_OWNER = "owner"
ROLE_GUEST = "guest"
ROLE_SHARE = "share"

# 游客允许的 endpoint（只读）
GUEST_ALLOWED_ENDPOINTS = frozenset(
    {
        "auth.login",
        "auth.logout",
        "auth.enter_guest",
        "auth.share_enter",
        "static",
        "poems_page",
        "notes.notes_list",
        "notes.notes_view",
        "notes.notes_asset",
    }
)

POEMS_READ_ENDPOINTS = frozenset({"poems_page"})

BILLS_ENDPOINTS = frozenset(
    {
        "import_page",
        "records_page",
        "analysis_page",
        "types_page",
        "travel_page",
        "journal_page",
        "staging_page",
        "download_backup_zip",
        "download_template_csv",
        "download_template_xlsx",
        "api_backup_latest",
        "api_backup_file",
    }
)


def access_password() -> str:
    return env_password()


def auth_enabled() -> bool:
    return auth_configured()


def access_role() -> str | None:
    role = session.get("access_role")
    if role in (ROLE_OWNER, ROLE_GUEST, ROLE_SHARE):
        return role
    if session.get("bill_auth_ok"):
        return ROLE_OWNER
    return None


def is_owner() -> bool:
    role = access_role()
    if not auth_enabled():
        return role != ROLE_GUEST and role != ROLE_SHARE
    return role == ROLE_OWNER


def is_guest() -> bool:
    return access_role() == ROLE_GUEST


def is_share() -> bool:
    return access_role() == ROLE_SHARE


def share_modules() -> list[str]:
    if not is_share():
        return []
    mods = session.get("share_modules")
    if isinstance(mods, list):
        return [m for m in mods if m in SITE_MODULES]
    return []


def share_profile_name() -> str:
    if not is_share():
        return ""
    return str(session.get("share_profile_name") or "分享访问")


def has_site_access() -> bool:
    return access_role() in (ROLE_OWNER, ROLE_GUEST, ROLE_SHARE)


def is_logged_in() -> bool:
    if not auth_enabled():
        return not is_guest() and not is_share()
    return is_owner()


def has_module_access(module: str) -> bool:
    if is_owner():
        return True
    if is_guest():
        return module in ("poems", "notes")
    if is_share():
        return module in share_modules()
    return False


def can_write() -> bool:
    return is_owner()


def module_home_url(module: str) -> str:
    spec = SITE_MODULES.get(module) or SITE_MODULES["poems"]
    return url_for(spec["home"])


def share_home_url() -> str:
    mods = share_modules()
    if mods:
        return module_home_url(mods[0])
    return url_for("auth.login")


def home_url() -> str:
    if is_guest():
        return url_for("poems_page")
    if is_share():
        return share_home_url()
    return url_for("import_page")


def safe_next(raw: str | None) -> str:
    nxt = (raw or "").strip()
    if nxt.startswith("/") and not nxt.startswith("//"):
        if is_share():
            mod = request_module(path=nxt)
            if mod and has_module_access(mod):
                return nxt
            return share_home_url()
        return nxt
    return home_url()


def _password_ok(pwd: str, expected: str) -> bool:
    a = hashlib.sha256(pwd.encode("utf-8")).digest()
    b = hashlib.sha256(expected.encode("utf-8")).digest()
    return secrets.compare_digest(a, b)


def request_module(endpoint: str | None = None, path: str | None = None) -> str | None:
    ep = endpoint or ""
    p = (path or request.path if path is None else path).split("?")[0]

    if ep.startswith("auth.") or ep == "static":
        return None
    if ep.startswith("collection.") or p.startswith("/collection"):
        return "collection"
    if ep.startswith("health.") or p.startswith("/health"):
        return "health"
    if ep.startswith("water.") or p.startswith("/water"):
        return "water"
    if ep.startswith("notes.") or p.startswith("/notes"):
        return "notes"
    if p.startswith("/settings/sharing") or p.startswith("/settings/access") or ep in (
        "auth.sharing_settings",
        "auth.access_settings",
    ):
        return "settings"
    if p.startswith("/poems") or (ep and ep.startswith("poem")):
        return "poems"
    if ep == "journal_page" or p == "/journal":
        return "journal"
    if (
        ep in BILLS_ENDPOINTS
        or p in ("/", "/records", "/analysis", "/types", "/travel", "/journal")
        or p.startswith("/staging")
        or p.startswith("/download")
        or p.startswith("/api/backup")
    ):
        return "bills"
    return None


def guest_can_access(endpoint: str | None) -> bool:
    if not endpoint:
        return False
    return endpoint in GUEST_ALLOWED_ENDPOINTS


def share_can_access(endpoint: str | None, path: str | None = None) -> bool:
    mod = request_module(endpoint, path)
    if mod is None:
        return True
    if mod == "settings":
        return False
    if not has_module_access(mod):
        return False
    if mod == "poems" and endpoint and endpoint not in POEMS_READ_ENDPOINTS:
        return False
    return True


def _apply_share_profile(profile: dict) -> None:
    session.clear()
    session["access_role"] = ROLE_SHARE
    session.update(profile_session_payload(profile))
    session.permanent = True


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

        if mode == "share":
            pwd = (request.form.get("share_password") or request.form.get("password") or "").strip()
            profile = find_profile_by_password(pwd)
            if profile:
                _apply_share_profile(profile)
                flash(f"欢迎，{profile.get('name') or '朋友'}（分享浏览）", "success")
                return redirect(safe_next(nxt) if nxt else share_home_url())
            error = "分享密码无效"
            return render_template(
                "auth/login.html",
                error=error,
                next=nxt,
                auth_enabled=auth_enabled(),
            )

        # owner
        if not auth_enabled():
            session.clear()
            session["access_role"] = ROLE_OWNER
            session.permanent = True
            return redirect(safe_next(nxt) if nxt else url_for("import_page"))

        pwd = (request.form.get("password") or "").strip()
        if verify_owner_password(pwd):
            session.clear()
            session["access_role"] = ROLE_OWNER
            session["bill_auth_ok"] = True
            session.permanent = True
            return redirect(safe_next(nxt) if nxt else url_for("import_page"))
        error = "密码错误"
        return render_template(
            "auth/login.html",
            error=error,
            next=nxt,
            auth_enabled=auth_enabled(),
        )

    if access_role() == ROLE_OWNER:
        return redirect(safe_next(nxt) if nxt else url_for("import_page"))
    if access_role() == ROLE_GUEST:
        return redirect(url_for("poems_page"))
    if access_role() == ROLE_SHARE:
        return redirect(safe_next(nxt) if nxt else share_home_url())

    return render_template(
        "auth/login.html",
        error=error,
        next=nxt,
        auth_enabled=auth_enabled(),
    )


@auth_bp.route("/share/<token>")
def share_enter(token: str):
    profile = find_profile_by_token(token)
    if not profile:
        flash("分享链接无效或已失效", "error")
        return redirect(url_for("auth.login"))
    _apply_share_profile(profile)
    flash(f"欢迎，{profile.get('name') or '朋友'}（分享浏览）", "success")
    return redirect(share_home_url())


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


@auth_bp.route("/settings/access", methods=["GET", "POST"])
@auth_bp.route("/settings/sharing", methods=["GET", "POST"])
def access_settings():
    if not is_owner():
        abort(403)

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "delete":
            pid = (request.form.get("profile_id") or "").strip()
            if delete_profile(pid):
                flash("已删除分享配置", "success")
            else:
                flash("未找到该分享配置", "error")
        elif action == "create":
            try:
                _, plain = create_profile(
                    name=(request.form.get("name") or "").strip(),
                    password=(request.form.get("password") or "").strip() or None,
                    modules=request.form.getlist("modules"),
                )
                session["share_created_password"] = plain
                flash("已创建分享访问", "success")
            except ValueError as exc:
                flash(str(exc), "error")
        elif action == "update":
            try:
                if update_profile(
                    (request.form.get("profile_id") or "").strip(),
                    (request.form.get("name") or "").strip(),
                    request.form.getlist("modules"),
                ):
                    flash("已更新分享配置", "success")
                else:
                    flash("未找到该分享配置", "error")
            except ValueError as exc:
                flash(str(exc), "error")
        elif action == "reset_password":
            pid = (request.form.get("profile_id") or "").strip()
            result = reset_profile_password(pid)
            if result:
                session["share_created_password"] = result[1]
                flash("已重置分享密码", "success")
            else:
                flash("未找到该分享配置", "error")
        elif action == "regenerate_link":
            pid = (request.form.get("profile_id") or "").strip()
            if regenerate_profile_token(pid):
                flash("已重新生成专属链接（旧链接失效）", "success")
            else:
                flash("未找到该分享配置", "error")
        elif action == "change_owner_password":
            try:
                current = (request.form.get("current_password") or "").strip()
                new_pwd = (request.form.get("new_password") or "").strip()
                if auth_enabled() and not current:
                    raise ValueError("请填写当前密码")
                set_owner_password(current, new_pwd)
                flash("所有者密码已更新", "success")
            except ValueError as exc:
                flash(str(exc), "error")
        return redirect(url_for("auth.access_settings"))

    profiles = list_profiles_public()
    rows = []
    for p in profiles:
        mods = p.get("modules") or []
        token = p.get("token") or ""
        if os.environ.get("BILL_COOKIE_SECURE", "").strip() in ("1", "true", "yes"):
            share_url = url_for("auth.share_enter", token=token, _external=True, _scheme="https")
        else:
            share_url = url_for("auth.share_enter", token=token, _external=True)
        rows.append(
            {
                **p,
                "module_labels": [SITE_MODULES[m]["label"] for m in mods if m in SITE_MODULES],
                "share_url": share_url,
            }
        )
    created_password = session.pop("share_created_password", "")
    return render_template(
        "settings/access.html",
        profiles=rows,
        modules=SITE_MODULES,
        created_password=created_password,
        password_from_env=password_managed_by_env(),
        auth_on=auth_enabled(),
    )


# 兼容旧 endpoint 名
sharing_settings = access_settings


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_owner():
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def owner_required(view):
    return login_required(view)
