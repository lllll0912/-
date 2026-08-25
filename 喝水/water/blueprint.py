"""喝水提醒（网站版）Blueprint。"""

from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .schedule_util import find_next_slot, parse_hhmm, today_slots_preview
from .store import DataStore
from .timeutil import format_hm, format_hms, format_record_clock, now_cn

water_bp = Blueprint(
    "water",
    __name__,
    url_prefix="/water",
    template_folder="templates",
    static_folder="static",
    static_url_path="/water-static",
)


def _store() -> DataStore:
    return DataStore()


def _next_slot_dt(store: DataStore):
    if not store.settings.reminder_enabled:
        return None
    try:
        h, m = parse_hhmm(store.settings.schedule_start)
    except ValueError:
        return None
    return find_next_slot(now_cn(), h, m, store.settings.schedule_interval_hours)


def _next_slot_iso(store: DataStore) -> str | None:
    nxt = _next_slot_dt(store)
    return nxt.isoformat(timespec="seconds") if nxt else None


def _motivate(pct: int, total: int, goal: int) -> str:
    if total <= 0:
        return "身体在等你的第一口水，现在就来一杯。"
    if pct < 30:
        return "开了个好头，清澈感正在回来。"
    if pct < 60:
        return "节奏不错，稳住，继续润一润。"
    if pct < 90:
        return "快满杯了，再一口就更接近目标。"
    if pct < 100:
        return "就差临门一脚，达标就在眼前。"
    return "今日达标！继续保持这份清爽。"


def _status_payload(store: DataStore) -> dict:
    today = now_cn().date()
    total = store.daily_total_ml(today)
    goal = store.settings.daily_goal_ml
    pct = min(100, int(round(100 * total / goal))) if goal else 0
    nxt = _next_slot_dt(store)
    now = now_cn()
    return {
        "today_total": total,
        "goal": goal,
        "pct": pct,
        "cup_ml": store.settings.cup_ml,
        "reminder_enabled": store.settings.reminder_enabled,
        "next_slot": nxt.isoformat(timespec="seconds") if nxt else None,
        "next_slot_hm": format_hm(nxt) if nxt else "",
        "server_now": now.isoformat(timespec="seconds"),
        "server_now_hms": format_hms(now),
        "motivate": _motivate(pct, total, goal),
    }


@water_bp.route("/")
def water_home():
    store = _store()
    today = now_cn().date()
    total = store.daily_total_ml(today)
    goal = store.settings.daily_goal_ml
    pct = min(100, int(round(100 * total / goal))) if goal else 0
    raw_records = sorted(store.records_on_date(today), key=lambda r: r.timestamp, reverse=True)
    records = [
        {
            "id": r.id,
            "amount_ml": r.amount_ml,
            "time_label": format_record_clock(r.timestamp),
        }
        for r in raw_records
    ]
    try:
        h, m = parse_hhmm(store.settings.schedule_start)
        slots = today_slots_preview(h, m, store.settings.schedule_interval_hours)
    except ValueError:
        slots = ""
    nxt = _next_slot_dt(store)
    now = now_cn()
    return render_template(
        "water/home.html",
        settings=store.settings,
        today_total=total,
        goal=goal,
        pct=pct,
        records=records,
        next_slot=nxt.isoformat(timespec="seconds") if nxt else None,
        next_slot_hm=format_hm(nxt) if nxt else "",
        server_now=now.isoformat(timespec="seconds"),
        today_label=now.strftime("%Y-%m-%d"),
        weekday_label=["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
        motivate=_motivate(pct, total, goal),
        slots_preview=slots,
        remaining_ml=max(0, goal - total),
    )


@water_bp.route("/widget")
def water_widget():
    """独立网页小窗：可被 window.open 弹出，交互走网站会话。"""
    store = _store()
    return render_template("water/widget.html", **_status_payload(store), settings=store.settings)


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
    flash("已记录 {} ml · 清爽一点".format(amount), "success")
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
    return render_template("water/settings.html", settings=store.settings)


@water_bp.route("/history")
def water_history():
    store = _store()
    series = store.aggregate_by_day(limit=30)
    max_ml = max((x["total_ml"] for x in series), default=0) or 1
    return render_template(
        "water/history.html",
        series=series,
        max_ml=max_ml,
        goal=store.settings.daily_goal_ml,
    )
