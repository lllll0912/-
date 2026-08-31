"""健康档案 Blueprint（仅所有者）。"""

from __future__ import annotations

import mimetypes
import os
from datetime import date

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from auth import can_write, has_module_access, is_owner

from .store import (
    add_uploaded_record,
    build_patient_tabs,
    build_year_calendar,
    get_record,
    list_records,
    load_doc_categories,
    load_patients,
    load_purpose_tags,
    normalize_patient_scope,
    person_label,
    resolve_asset,
    update_record_meta,
    year_choices,
)
from .github_sync import sync_status_label


health_bp = Blueprint(
    "health",
    __name__,
    url_prefix="/health",
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)


def _owner_or_403():
    if not is_owner():
        abort(403)


def _flash_upload_ok(rec: dict) -> None:
    path = rec.get("github_path") or rec.get("file_name") or ""
    mode = sync_status_label()
    who = person_label(str(rec.get("person") or "self"))
    if mode == "github":
        flash(f"已上传（{who}）并写入 GitHub：{path}", "success")
    elif mode == "local":
        flash(f"已上传（{who}）到本机 {path}。请 git push 同步私密仓。", "success")
    else:
        flash(
            f"已上传到服务器缓存：{path}。尚未配置 HEALTH_GITHUB_TOKEN，文件还没进 GitHub。",
            "error",
        )


@health_bp.before_request
def _guard():
    if request.endpoint and request.endpoint.endswith(".static"):
        return None
    if not has_module_access("health"):
        abort(403)
    if request.method not in ("GET", "HEAD") and not is_owner():
        abort(403)


def _filter_args():
    purpose = (request.args.get("purpose") or request.form.get("purpose") or "").strip()
    q = (request.args.get("q") or "").strip()
    cats = [c.strip() for c in request.args.getlist("category") if c.strip()]
    if not cats:
        one = (request.args.get("category") or "").strip()
        if one:
            cats = [one]
    patient = normalize_patient_scope(
        request.args.get("patient") or request.form.get("patient") or "self"
    )
    return purpose, q, cats, patient


@health_bp.route("/")
def health_home():
    return redirect(url_for("health.health_calendar"))


@health_bp.route("/calendar", methods=["GET", "POST"])
def health_calendar():
    # 上传表单 POST 到本页
    if request.method == "POST" and (request.form.get("action") or "") == "upload":
        cats = [c.strip() for c in request.form.getlist("category") if c.strip()]
        person_id = (request.form.get("person") or "self").strip() or "self"
        if person_id == "family":
            person_id = "zhangyue"
        rec, err = add_uploaded_record(
            file_storage=request.files.get("file"),
            exam_date=(request.form.get("exam_date") or "").strip(),
            categories=cats,
            exam_name=(request.form.get("exam_name") or "").strip(),
            notes=(request.form.get("notes") or "").strip(),
            purpose=(request.form.get("purpose") or "").strip(),
            purpose_note=(request.form.get("purpose_note") or "").strip(),
            hospital=(request.form.get("hospital") or "").strip(),
            person=person_id,
        )
        if err:
            flash(err, "error")
            return redirect(
                url_for("health.health_calendar", panel="upload", patient=person_id or "self")
            )
        _flash_upload_ok(rec or {})
        y = (rec.get("exam_date") or "")[:4]
        scope = normalize_patient_scope(str((rec or {}).get("person") or person_id or "self"))
        return redirect(url_for("health.health_calendar", year=y or None, patient=scope))

    purpose, q, cats, patient = _filter_args()
    records = list_records(person=patient, purpose=purpose, categories=cats, q=q)
    choices = year_choices(list_records(person=patient))
    raw = (request.args.get("year") or "").strip()
    if raw.isdigit():
        year = int(raw)
    else:
        year = choices[0] if choices else date.today().year
    cal = build_year_calendar(year, records)
    by_date = {}
    for month in cal["months"]:
        for week in month["weeks"]:
            for day in week:
                if day.get("empty") or not day.get("count"):
                    continue
                by_date[day["date"]] = day["records"]
    panel = (request.args.get("panel") or "").strip()
    return render_template(
        "calendar.html",
        cal=cal,
        years=choices,
        year=year,
        purpose_tags=load_purpose_tags(),
        doc_categories=load_doc_categories(),
        upload_categories=[c for c in load_doc_categories() if c.get("upload")],
        patients=[p for p in load_patients() if p["id"] != "family"],
        patient_tabs=build_patient_tabs(),
        day_data=by_date,
        filters={"purpose": purpose, "categories": cats, "q": q, "patient": patient},
        patient=patient,
        patient_label=person_label(patient) if patient != "family" else "家人",
        panel=panel,
        save_url_template=url_for("health.health_record_save", record_id="__ID__"),
        is_local=not bool((os.environ.get("BILL_DATA_DIR") or "").strip()),
        sync_mode=sync_status_label(),
    )


@health_bp.route("/upload", methods=["GET", "POST"])
def health_upload():
    # 兼容旧链接：并入日历页
    if request.method == "POST":
        cats = [c.strip() for c in request.form.getlist("category") if c.strip()]
        rec, err = add_uploaded_record(
            file_storage=request.files.get("file"),
            exam_date=(request.form.get("exam_date") or "").strip(),
            categories=cats,
            exam_name=(request.form.get("exam_name") or "").strip(),
            notes=(request.form.get("notes") or "").strip(),
            purpose=(request.form.get("purpose") or "").strip(),
            purpose_note=(request.form.get("purpose_note") or "").strip(),
            hospital=(request.form.get("hospital") or "").strip(),
        )
        if err:
            flash(err, "error")
            return redirect(url_for("health.health_calendar", panel="upload"))
        _flash_upload_ok(rec or {})
        y = (rec.get("exam_date") or "")[:4]
        return redirect(url_for("health.health_calendar", year=y or None))
    return redirect(url_for("health.health_calendar", panel="upload"))


@health_bp.route("/records")
def health_records():
    return redirect(url_for("health.health_calendar", panel="search"))


@health_bp.route("/timeline")
def health_timeline():
    return redirect(url_for("health.health_calendar"))


@health_bp.route("/records/<record_id>/save", methods=["POST"])
def health_record_save(record_id: str):
    rec = get_record(record_id)
    next_url = (request.form.get("next") or "").strip()
    year = (request.form.get("year") or "").strip()
    if not rec:
        flash("未找到该档案", "error")
        return redirect(url_for("health.health_calendar", year=year or None))
    cats = [c.strip() for c in request.form.getlist("category") if c.strip()]
    if update_record_meta(
        record_id,
        purpose=(request.form.get("purpose") or "").strip(),
        purpose_note=(request.form.get("purpose_note") or "").strip(),
        result_status=(request.form.get("result_status") or "").strip(),
        categories=cats or None,
        notes=(request.form.get("notes") or "").strip(),
        exam_name=(request.form.get("exam_name") or "").strip() or None,
        person=(request.form.get("person") or "").strip() or None,
    ):
        flash("已保存标注", "success")
    else:
        flash("保存失败", "error")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("health.health_calendar", year=year or None))


@health_bp.route("/records/<record_id>", methods=["GET", "POST"])
def health_record_detail(record_id: str):
    return redirect(url_for("health.health_calendar"))


@health_bp.route("/file/<path:relpath>")
def health_file(relpath: str):
    path = resolve_asset(relpath)
    if not path:
        abort(404)
    download = (request.args.get("download") or "").strip() in ("1", "true", "yes")
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return send_file(
        path,
        mimetype=mime,
        as_attachment=download,
        download_name=path.name if download else None,
        max_age=86400 if not download else 0,
    )
