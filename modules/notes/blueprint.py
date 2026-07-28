"""笔记专栏 Blueprint。"""

from __future__ import annotations

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from auth import is_guest, is_owner

from .store import (
    create_note,
    delete_note,
    get_note,
    list_notes,
    load_md_hints,
    resolve_asset,
    save_md_hints,
    save_note_image,
    update_note,
)

notes_bp = Blueprint("notes", __name__, url_prefix="/notes")


def _owner_or_403():
    if not is_owner():
        abort(403)


@notes_bp.route("/")
def notes_list():
    notes = list_notes()
    return render_template(
        "notes_list.html",
        notes=notes,
        can_edit=is_owner(),
        is_guest=is_guest(),
    )


@notes_bp.route("/new", methods=["GET", "POST"])
def notes_new():
    """新建：先落库草稿再进编辑页，便于立刻上传图片。"""
    _owner_or_403()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = request.form.get("content_md") or ""
        note_id = create_note(title, content)
        flash("已创建笔记", "success")
        return redirect(url_for("notes.notes_edit", note_id=note_id))
    note_id = create_note("未命名笔记", "")
    return redirect(url_for("notes.notes_edit", note_id=note_id))


@notes_bp.route("/<int:note_id>")
def notes_view(note_id: int):
    note = get_note(note_id)
    if not note:
        flash("笔记不存在", "error")
        return redirect(url_for("notes.notes_list"))
    return render_template(
        "notes_view.html",
        note=note,
        can_edit=is_owner(),
    )


@notes_bp.route("/<int:note_id>/edit", methods=["GET", "POST"])
def notes_edit(note_id: int):
    _owner_or_403()
    note = get_note(note_id)
    if not note:
        flash("笔记不存在", "error")
        return redirect(url_for("notes.notes_list"))
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = request.form.get("content_md") or ""
        update_note(note_id, title, content)
        flash("已保存", "success")
        return redirect(url_for("notes.notes_view", note_id=note_id))
    return render_template(
        "notes_edit.html",
        note=note,
        can_edit=True,
        md_hints=load_md_hints(),
    )


@notes_bp.route("/md-hints", methods=["GET", "POST"])
def notes_md_hints():
    """Markdown 速查提示：所有者可读写，持久在 data/notes_md_hints.json。"""
    if request.method == "GET":
        return jsonify({"ok": True, "items": load_md_hints()})
    _owner_or_403()
    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list):
        return jsonify({"ok": False, "msg": "格式错误"}), 400
    saved = save_md_hints(items)
    return jsonify({"ok": True, "items": saved})


@notes_bp.route("/<int:note_id>/delete", methods=["POST"])
def notes_delete(note_id: int):
    _owner_or_403()
    if delete_note(note_id):
        flash("已删除笔记", "success")
    else:
        flash("未找到笔记", "error")
    return redirect(url_for("notes.notes_list"))


@notes_bp.route("/<int:note_id>/upload", methods=["POST"])
def notes_upload(note_id: int):
    _owner_or_403()
    if not get_note(note_id):
        return jsonify({"ok": False, "msg": "笔记不存在"}), 404
    f = request.files.get("file") or request.files.get("image")
    if not f or not f.filename:
        return jsonify({"ok": False, "msg": "未选择文件"}), 400
    data = f.read()
    try:
        url = save_note_image(note_id, f.filename, data)
    except ValueError as exc:
        return jsonify({"ok": False, "msg": str(exc)}), 400
    return jsonify({"ok": True, "url": url, "data": {"url": url}})


@notes_bp.route("/assets/<int:note_id>/<path:filename>")
def notes_asset(note_id: int, filename: str):
    # 游客与所有者均可读已发布笔记配图
    path = resolve_asset(note_id, filename)
    if not path:
        abort(404)
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(filename.rsplit(".", 1)[-1].lower(), "application/octet-stream")
    return Response(path.read_bytes(), mimetype=mime)
