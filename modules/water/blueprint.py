"""喝水提醒（网站版）Blueprint。"""

from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .schedule_util import find_next_slot, parse_hhmm, today_slots_preview
from .store import DataStore

water_bp = Blueprint("water", __name__, url_prefix="/water")


def _store() -> DataStore:
    return DataStore()


def _next_slot_iso(store: DataStore) -> str | None:
    if not store.settings.reminder_enabled:
        return None
    try:
        h, m = parse_hhmm(store.settings.schedule_start)
    except ValueError:
        return None
    nxt = find_next_slot(datetime.now(), h, m, store.settings.schedule_interval_hours)
    return nxt.isoformat(timespec="seconds")


def _status_payload(store: DataStore) -> dict:
    today = date.today()
    total = store.daily_total_ml(today)
    goal = store.settings.daily_goal_ml
    pct = min(100, int(round(100 * total / goal))) if goal else 0
    return {
        "today_total": total,
        "goal": goal,
        "pct": pct,
        "cup_ml": store.settings.cup_ml,
        "reminder_enabled": store.settings.reminder_enabled,
        "next_slot": _next_slot_iso(store),
        "server_now": datetime.now().isoformat(timespec="seconds"),
    }


@water_bp.route("/")
def water_home():
    store = _store()
    today = date.today()
    total = store.daily_total_ml(today)
    goal = store.settings.daily_goal_ml
    pct = min(100, int(round(100 * total / goal))) if goal else 0
    records = sorted(store.records_on_date(today), key=lambda r: r.timestamp, reverse=True)
    try:
        h, m = parse_hhmm(store.settings.schedule_start)
        slots = today_slots_preview(h, m, store.settings.schedule_interval_hours)
    except ValueError:
        slots = ""
    return render_template(
        "water.html",
        settings=store.settings,
        today_total=total,
        goal=goal,
        pct=pct,
        records=records,
        next_slot=_next_slot_iso(store),
        slots_preview=slots,
    )


@water_bp.route("/widget")
def water_widget():
    """独立网页小窗：可被 window.open 弹出，交互走网站会话。"""
    store = _store()
    return render_template("water_widget.html", **_status_payload(store), settings=store.settings)


@water_bp.route("/api/status")
def water_api_status():
    return jsonify(_status_payload(_store()))


@water_bp.route("/api/drink", methods=["POST"])
def water_api_drink():
    store = _store()
    payload = request.get_json(silent=True) or {}
    raw = request.form.get("amount_ml")
    if raw is None:
        raw = payload.get("amount_ml")
    try:
        amount = int(raw) if raw not in (None, "") else int(store.settings.cup_ml)
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "杯量无效"}), 400
    if amount <= 0 or amount > 5000:
        return jsonify({"ok": False, "error": "杯量需在 1–5000 ml"}), 400
    store.add_record(amount)
    return jsonify({"ok": True, "amount_ml": amount, **_status_payload(store)})


@water_bp.route("/drink", methods=["POST"])
def water_drink():
    store = _store()
    raw = (request.form.get("amount_ml") or "").strip()
    try:
        amount = int(raw) if raw else int(store.settings.cup_ml)
    except ValueError:
        flash("杯量无效", "error")
        return redirect(url_for("water.water_home"))
    if amount <= 0 or amount > 5000:
        flash("杯量需在 1–5000 ml", "error")
        return redirect(url_for("water.water_home"))
    store.add_record(amount)
    flash("已记录 {} ml".format(amount), "success")
    nxt = (request.form.get("next") or "").strip()
    if nxt == "widget":
        return redirect(url_for("water.water_widget"))
    return redirect(url_for("water.water_home"))


@water_bp.route("/records/<record_id>/delete", methods=["POST"])
def water_delete_record(record_id: str):
    store = _store()
    if store.delete_record(record_id):
        flash("已删除这条记录", "success")
    else:
        flash("未找到记录", "error")
    nxt = (request.form.get("next") or "").strip()
    if nxt == "history":
        return redirect(url_for("water.water_history"))
    return redirect(url_for("water.water_home"))


@water_bp.route("/settings", methods=["GET", "POST"])
def water_settings():
    store = _store()
    if request.method == "POST":
        try:
            start = (request.form.get("schedule_start") or "09:30").strip()
            parse_hhmm(start)
            interval = float(request.form.get("schedule_interval_hours") or 1.5)
            cup = int(request.form.get("cup_ml") or 250)
            goal = int(request.form.get("daily_goal_ml") or 2000)
            if interval <= 0 or interval > 12:
                raise ValueError("间隔无效")
            if cup <= 0 or goal <= 0:
                raise ValueError("杯量或目标无效")
            store.update_settings(
                schedule_start=start,
                schedule_interval_hours=interval,
                cup_ml=cup,
                daily_goal_ml=goal,
                reminder_enabled=bool(request.form.get("reminder_enabled")),
            )
            flash("设置已保存", "success")
            return redirect(url_for("water.water_settings"))
        except (ValueError, TypeError) as exc:
            flash("保存失败：{}".format(exc), "error")
    return render_template("water_settings.html", settings=store.settings)


@water_bp.route("/history")
def water_history():
    store = _store()
    series = store.aggregate_by_day(limit=30)
    max_ml = max((x["total_ml"] for x in series), default=0) or 1
    return render_template(
        "water_history.html",
        series=series,
        max_ml=max_ml,
        goal=store.settings.daily_goal_ml,
    )
