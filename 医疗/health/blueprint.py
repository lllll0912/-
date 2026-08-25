"""健康档案 Blueprint（仅所有者）。"""

from __future__ import annotations

import mimetypes
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

from auth import is_owner

from .store import (
    build_year_calendar,
    get_record,
    group_events,
    list_records,
    load_purpose_tags,
    resolve_asset,
    update_record_meta,
    year_choices,
)

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


@health_bp.before_request
def _guard():
    if request.endpoint and request.endpoint.endswith(".static"):
        return None
    _owner_or_403()


@health_bp.route("/")
def health_home():
    return redirect(url_for("health.health_calendar"))


@health_bp.route("/calendar")
def health_calendar():
    records = list_records(person="self")
    choices = year_choices(records)
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
    return render_template(
        "calendar.html",
        cal=cal,
        years=choices,
        year=year,
        purpose_tags=load_purpose_tags(),
        day_data=by_date,
        save_url_template=url_for("health.health_record_save", record_id="__ID__"),
    )


@health_bp.route("/timeline")
def health_timeline():
    purpose = (request.args.get("purpose") or "").strip()
    category = (request.args.get("category") or "").strip()
    records = list_records(person="self", purpose=purpose, category=category)
    events = group_events(records)
    return render_template(
        "timeline.html",
        events=events,
        filters={"purpose": purpose, "category": category},
        purpose_tags=load_purpose_tags(),
    )


@health_bp.route("/records")
def health_records():
    purpose = (request.args.get("purpose") or "").strip()
    category = (request.args.get("category") or "").strip()
    records = list_records(person="self", purpose=purpose, category=category)
    return render_template(
        "records.html",
        records=records,
        filters={"purpose": purpose, "category": category},
        purpose_tags=load_purpose_tags(),
    )


@health_bp.route("/records/<record_id>/save", methods=["POST"])
def health_record_save(record_id: str):
    rec = get_record(record_id)
    next_url = (request.form.get("next") or "").strip()
    year = (request.form.get("year") or "").strip()
    if not rec:
        flash("未找到该档案", "error")
        return redirect(url_for("health.health_calendar", year=year or None))
    purpose = (request.form.get("purpose") or "").strip()
    note = (request.form.get("purpose_note") or "").strip()
    result_status = (request.form.get("result_status") or "").strip()
    if update_record_meta(
        record_id,
        purpose=purpose,
        purpose_note=note,
        result_status=result_status,
    ):
        flash("已保存标注", "success")
    else:
        flash("保存失败", "error")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("health.health_calendar", year=year or None))


@health_bp.route("/records/<record_id>", methods=["GET", "POST"])
def health_record_detail(record_id: str):
    rec = get_record(record_id)
    if not rec:
        flash("未找到该档案", "error")
        return redirect(url_for("health.health_calendar"))
    if request.method == "POST":
        purpose = (request.form.get("purpose") or "").strip()
        note = (request.form.get("purpose_note") or "").strip()
        result_status = (request.form.get("result_status") or "").strip()
        if update_record_meta(
            record_id,
            purpose=purpose,
            purpose_note=note,
            result_status=result_status,
        ):
            flash("已保存", "success")
        else:
            flash("更新失败", "error")
        y = (rec.get("exam_date") or "")[:4]
        return redirect(url_for("health.health_calendar", year=y or None))
    return render_template(
        "detail.html",
        record=rec,
        purpose_tags=load_purpose_tags(),
    )


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
        max_age=0,
    )
