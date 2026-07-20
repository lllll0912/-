from pathlib import Path
import json
import os
from datetime import datetime, timedelta

from flask import Flask, redirect, render_template, request, url_for, flash
from flask import Response, session

from auth import auth_bp, auth_enabled, is_logged_in
from db.backup import write_latest_backup_csv
from offline_report import collect_payload, render_report_html
from db.repository import (
    backfill_category_l1,
    confirm_batch,
    create_import_batch,
    delete_records_by_date,
    delete_records_by_dates,
    delete_records_by_date_range,
    delete_staging_by_date,
    delete_staging_by_ids,
    delete_staging_record,
    daily_heatmap_data,
    get_batch,
    insert_staging_records,
    list_available_years,
    list_batches,
    list_bill_dates,
    list_categories,
    list_l1_categories,
    list_records,
    list_staging_records,
    summary_by_category_month,
    set_travel_tag_by_date_range,
    clear_travel_tag_by_date_range,
    set_travel_tag_by_dates,
    clear_travel_tag_by_dates,
    update_travel_companions_by_trip_tag,
    travel_tagged_dates,
    travel_summary,
    update_staging_record,
    update_record,
)
from db.schema import init_db
from importers import OPTIONAL_COLUMNS, REQUIRED_COLUMNS, parse_input_to_staging
from parser import ImportOptions
from preview_store import create_preview, get_preview, pop_preview, update_preview
from rule_manager import (
    category_options,
    category_options_grouped,
    is_known_category,
    is_known_l1,
    l2_to_l1,
    learn_exact_detail,
    list_rule_rows,
    upsert_rule,
    delete_rule,
    load_rules,
)


app = Flask(__name__)
app.secret_key = os.environ.get("BILL_SECRET_KEY") or os.environ.get("SECRET_KEY") or "bill-dev-secret-change-me"
app.permanent_session_lifetime = timedelta(days=14)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# 公网 HTTPS 部署时设 BILL_COOKIE_SECURE=1，本机 HTTP 调试不要开
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("BILL_COOKIE_SECURE", "").strip() in ("1", "true", "yes")
app.register_blueprint(auth_bp)

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_PATH = BASE_DIR / "Transfer Dock_Text_20260318112028.txt"
if not SAMPLE_PATH.exists():
    SAMPLE_PATH = BASE_DIR / "1.待规则化年份账单" / "2025账单.txt"
db_ready = False


@app.before_request
def _require_login():
    if not auth_enabled():
        return None
    if request.endpoint and (
        request.endpoint.startswith("auth.")
        or request.endpoint == "static"
    ):
        return None
    if is_logged_in():
        return None
    return redirect(url_for("auth.login", next=request.path))


@app.context_processor
def _inject_auth():
    return {"auth_enabled": auth_enabled(), "is_logged_in": is_logged_in()}



def ensure_db():
    global db_ready
    if not db_ready:
        init_db()
        _migrate_l1()
        db_ready = True


def _migrate_l1():
    """首次启动时，用当前规则为 category_l1 为空的旧记录回填。"""
    try:
        rules = load_rules()
        l2map = {}
        for map_key in ("CONSUME_MAP", "INCOME_MAP"):
            for l1_name, subs in rules.get(map_key, {}).items():
                for l2_name in subs:
                    if l2_name not in l2map:
                        l2map[l2_name] = l1_name
        if l2map:
            backfill_category_l1(l2map)
    except Exception:
        pass


def _parse_id_list(raw: str):
    items = []
    for x in (raw or "").replace("，", ",").split(","):
        x = x.strip()
        if x.isdigit():
            items.append(int(x))
    return items


def _redirect_records_with_filters(form):
    return redirect(
        url_for(
            "records_page",
            direction=form.get("direction_filter", ""),
            category_l1=form.get("category_l1_filter", ""),
            category=form.get("category_filter", ""),
            is_travel=form.get("is_travel_filter", ""),
            keyword=form.get("keyword_filter", ""),
            dates=form.get("dates_filter", ""),
            sort_by=form.get("sort_by_filter", form.get("sort_by", "bill_date")),
            sort_order=form.get("sort_order_filter", form.get("sort_order", "desc")),
        )
    )


def _collect_detected_dates(rows):
    dates = sorted({str(r.get("bill_date")) for r in rows if r.get("bill_date")})
    return dates


def _parse_bill_year(raw: str) -> int:
    try:
        y = int((raw or "").strip())
        if 2000 <= y <= 2100:
            return y
    except Exception:
        pass
    return datetime.now().year


def _unknown_category_pairs(rows):
    seen = set()
    out = []
    for r in rows or []:
        d = str(r.get("direction", "")).strip()
        if d not in ("收入", "支出"):
            continue
        is_income = d == "收入"
        cat = str(r.get("category") or "").strip()
        raw = str(r.get("explicit_category_raw") or cat or "").strip()
        # 即使历史预览当时是“已知”，但用户后续编辑了字典（删除/改名），也要重新判定未知并提示映射
        cu = bool(r.get("category_unknown"))
        if cat and cat not in ("待分类", "待分类收入"):
            if (not is_known_category(cat, is_income)) and (not is_known_l1(cat, is_income)):
                cu = True
                if not raw:
                    raw = cat
                r["category_unknown"] = True
                r["explicit_category_raw"] = raw
        if not cu:
            continue
        if not raw or d not in ("收入", "支出"):
            continue
        key = "{}||{}".format(raw, d)
        if key in seen:
            continue
        seen.add(key)
        out.append({"raw": raw, "direction": d, "key": key})
    return out


def _preview_normalize_rows(raw_rows):
    out = []
    for idx, r in enumerate(raw_rows, start=1):
        bill_date = str(r.get("bill_date", "") or "").strip()
        if bill_date and len(bill_date) == 10:
            try:
                datetime.strptime(bill_date, "%Y-%m-%d")
            except Exception:
                bill_date = ""
        amount_raw = str(r.get("amount", "0")).strip()
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        direction = str(r.get("direction", "支出")).strip()
        if direction not in ("收入", "支出"):
            direction = "支出"
        detail = str(r.get("detail", "")).strip()
        note = str(r.get("note", "")).strip()
        category = str(r.get("category", "")).strip() or ("其他收入" if direction == "收入" else "其他消费")
        cat_l1 = str(r.get("category_l1", "")).strip()
        is_income = direction == "收入"
        explicit_raw = str(r.get("explicit_category_raw", "")).strip()
        cu = str(r.get("category_unknown", "0")).strip().lower() in ("1", "true", "yes")
        if is_known_category(category, is_income):
            cu = False
            explicit_raw = ""
            if not cat_l1:
                cat_l1 = l2_to_l1(category, is_income) or category
        elif is_known_l1(category, is_income):
            cu = False
            explicit_raw = ""
            cat_l1 = category
        elif cu and not explicit_raw:
            explicit_raw = category
        # 业务规则：导入清洗阶段不维护旅游字段，统一由“旅游管理”页面按日期维护
        is_travel = False
        travel_tag = ""
        errors = []
        if not bill_date:
            errors.append("日期格式错误")
        if detail == "":
            errors.append("类型明细不能为空")
        out.append(
            {
                "row_index": int(r.get("row_index", idx)),
                "bill_date": bill_date if bill_date else None,
                "amount": amount,
                "detail": detail,
                "note": note,
                "direction": direction,
                "category_l1": cat_l1,
                "category": category,
                "explicit_category_raw": explicit_raw if cu else "",
                "category_unknown": bool(cu),
                "is_travel": is_travel,
                "travel_tag": travel_tag if is_travel else "",
                "is_valid": len(errors) == 0,
                "error_msg": "；".join(errors),
            }
        )
    return out


@app.route("/", methods=["GET", "POST"])
def import_page():
    ensure_db()
    default_y = datetime.now().year
    year = _parse_bill_year(request.args.get("bill_year", str(default_y)))
    raw_text = request.values.get("raw_text", "")
    preview_token = request.args.get("preview_token", "")
    preview_data = get_preview(preview_token) if preview_token else None

    consume_grouped = category_options_grouped(False)
    income_grouped = category_options_grouped(True)

    if request.method == "POST":
        actions = request.form.getlist("action")
        action = actions[-1] if actions else "preview_parse"
        source_name = "文本导入"
        raw_text = request.form.get("raw_text", "")
        use_sample = request.form.get("use_sample", "") == "1"
        upload_file = request.files.get("txt_file")

        file_ext = ".txt"
        file_bytes = b""

        if action == "load_sample":
            year = _parse_bill_year(request.form.get("bill_year", str(default_y)))
            if SAMPLE_PATH.exists():
                raw_text = SAMPLE_PATH.read_text(encoding="utf-8")
                flash("已加载2025样例到账单文本框", "success")
            return render_template(
                "import.html",
                year=year,
                raw_text=raw_text,
                sample_loaded=True,
                batches=list_batches(limit=12),
                preview_token="",
                preview_data=None,
                detected_dates=[],
                min_date="",
                max_date="",
                unknown_category_pairs=[],
                required_columns=REQUIRED_COLUMNS,
                optional_columns=OPTIONAL_COLUMNS,
                consume_grouped=consume_grouped,
                income_grouped=income_grouped,
                consume_categories=category_options(False),
                income_categories=category_options(True),
            )

        if use_sample and SAMPLE_PATH.exists():
            raw_text = SAMPLE_PATH.read_text(encoding="utf-8")
            source_name = "2025样例账单"
            file_ext = ".txt"

        if upload_file and upload_file.filename:
            file_ext = Path(upload_file.filename).suffix.lower()
            file_bytes = upload_file.read()
            if file_ext == ".txt":
                raw_text = file_bytes.decode("utf-8", errors="ignore")
            source_name = upload_file.filename

        if action == "preview_parse":
            year = _parse_bill_year(request.form.get("bill_year", str(default_y)))
            if not raw_text.strip() and not file_bytes:
                flash("请先上传或粘贴账单文本", "error")
                return redirect(url_for("import_page"))

            rows, err = parse_input_to_staging(
                file_ext=file_ext,
                file_bytes=file_bytes,
                raw_text=raw_text,
                options=ImportOptions(year=year),
            )
            if err:
                flash("解析失败：{}".format(err), "error")
                return redirect(url_for("import_page"))

            token = create_preview(
                meta={
                    "source_name": source_name,
                    "source_year": year,
                    "raw_text": raw_text if raw_text else "[结构化文件导入]",
                },
                rows=rows,
            )
            unk = _unknown_category_pairs(rows)
            if unk:
                flash(
                    "已完成预清洗（共 {} 条）。另有 {} 种「文本中的类型」不在当前字典，请用下方「类型标准化映射」或表格中橙色行处理。".format(
                        len(rows), len(unk)
                    ),
                    "success",
                )
            else:
                flash("已完成预清洗，请检查并编辑预览数据", "success")
            return redirect(url_for("import_page", preview_token=token, bill_year=year))

        if action == "preview_apply_category_map":
            token = request.form.get("preview_token", "")
            data = get_preview(token)
            if not data:
                flash("预览数据已失效，请重新解析", "error")
                return redirect(url_for("import_page"))
            try:
                mp = json.loads(request.form.get("category_map_json", "") or "{}")
                if not isinstance(mp, dict):
                    raise ValueError("not object")
            except Exception:
                flash("类型映射 JSON 无效", "error")
                return redirect(url_for("import_page", preview_token=token))
            rows = data["rows"]
            changed = 0
            for r in rows:
                if not r.get("category_unknown"):
                    continue
                raw = str(r.get("explicit_category_raw") or "").strip()
                d = str(r.get("direction", ""))
                key = "{}||{}".format(raw, d)
                target = str(mp.get(key, "")).strip()
                if not target or not raw:
                    continue
                is_income = d == "收入"
                # 支持映射 token:
                # - L1::生活支出
                # - L2::医药
                # - 兼容旧值：直接二级类型名
                mapped_l1 = ""
                mapped_l2 = ""
                if target.startswith("L1::"):
                    v = target[4:].strip()
                    if not v or not is_known_l1(v, is_income):
                        continue
                    mapped_l1 = v
                    mapped_l2 = v
                elif target.startswith("L2::"):
                    v = target[4:].strip()
                    if not v or not is_known_category(v, is_income):
                        continue
                    mapped_l2 = v
                    mapped_l1 = l2_to_l1(v, is_income) or v
                else:
                    if not is_known_category(target, is_income):
                        continue
                    mapped_l2 = target
                    mapped_l1 = l2_to_l1(target, is_income) or target
                r["category"] = mapped_l2
                r["category_l1"] = mapped_l1
                r["category_unknown"] = False
                r["explicit_category_raw"] = ""
                changed += 1
            update_preview(token, rows)
            flash("已应用类型映射，更新 {} 行".format(changed), "success")
            ymeta = int(data.get("meta", {}).get("source_year", default_y))
            return redirect(url_for("import_page", preview_token=token, bill_year=ymeta))

        if action == "preview_delete_range":
            token = request.form.get("preview_token", "")
            data = get_preview(token)
            if not data:
                flash("预览数据已失效，请重新解析", "error")
                return redirect(url_for("import_page"))
            start_date = request.form.get("delete_start_date", "").strip()
            end_date = request.form.get("delete_end_date", "").strip()
            if not start_date or not end_date:
                flash("请先选择删除日期范围", "error")
                return redirect(url_for("import_page", preview_token=token))
            rows = data["rows"]
            before = len(rows)
            kept = []
            for r in rows:
                d = str(r.get("bill_date") or "")
                if d and start_date <= d <= end_date:
                    continue
                kept.append(r)
            update_preview(token, kept)
            flash("已按日期段删除：{} -> {}".format(before, len(kept)), "success")
            return redirect(url_for("import_page", preview_token=token))

        if action == "preview_save_rows":
            token = request.form.get("preview_token", "")
            data = get_preview(token)
            if not data:
                flash("预览数据已失效，请重新解析", "error")
                return redirect(url_for("import_page"))
            payload = request.form.get("rows_json", "")
            try:
                parsed = json.loads(payload)
                if not isinstance(parsed, list):
                    raise ValueError("rows_json not list")
            except Exception:
                flash("保存失败：预览数据格式错误", "error")
                return redirect(url_for("import_page", preview_token=token))
            normalized = _preview_normalize_rows(parsed)
            old_map = {}
            for r in data["rows"]:
                old_map[int(r.get("row_index", 0))] = r
            learned = 0
            for r in normalized:
                idx = int(r.get("row_index", 0))
                old = old_map.get(idx, {})
                old_cat = str(old.get("category", ""))
                new_cat = str(r.get("category", ""))
                new_l1 = str(r.get("category_l1", ""))
                detail = str(r.get("detail", ""))
                is_income = str(r.get("direction", "支出")) == "收入"
                old_unk = bool(old.get("category_unknown"))
                if new_cat not in ("", "待分类", "待分类收入") and is_known_category(new_cat, is_income):
                    if (old_unk or old_cat in ("待分类", "待分类收入")) and learn_exact_detail(
                        detail, new_cat, is_income, new_l1
                    ):
                        learned += 1
            update_preview(token, normalized)
            flash("已保存全部预览修改；自动学习新增规则 {} 条".format(learned), "success")
            return redirect(url_for("import_page", preview_token=token))

        if action == "create_staging_and_confirm":
            token = request.form.get("preview_token", "")
            data = get_preview(token)
            if not data:
                flash("预览数据已失效，请重新解析", "error")
                return redirect(url_for("import_page"))
            meta = data["meta"]
            rows = data["rows"]
            if not rows:
                flash("预览记录为空，无法生成临时表", "error")
                return redirect(url_for("import_page"))
            if any(r.get("category_unknown") for r in rows):
                flash(
                    "仍有「未映射类型」的行：请先在「类型标准化映射」中映射，或把类型改成字典里的标准类型后再入库。",
                    "error",
                )
                return redirect(url_for("import_page", preview_token=token))
            pop_preview(token)
            batch_id = create_import_batch(
                source_name=meta.get("source_name", "手动导入"),
                source_year=int(meta.get("source_year", default_y)),
                raw_text=str(meta.get("raw_text", "")),
            )
            insert_staging_records(batch_id, rows)
            import_mode = request.form.get("import_mode", "replace").strip()
            replace_existing = import_mode != "insert_only"
            result = confirm_batch(batch_id, replace_existing=replace_existing)
            backup_file = write_latest_backup_csv()
            if replace_existing:
                flash(
                    "已确认生成临时表并入库（覆盖模式）：新增 {} 条，覆盖删除旧记录 {} 条".format(
                        result["inserted"], result["replaced_deleted"]
                    ),
                    "success",
                )
            else:
                flash(
                    "已确认生成临时表并入库（仅插入模式）：新增 {} 条，未删除旧记录".format(
                        result["inserted"]
                    ),
                    "success",
                )
            if int(result.get("travel_reapplied", 0)) > 0:
                flash("已按旅游管理的日期打标规则回填旅游标签：{} 条".format(result["travel_reapplied"]), "success")
            flash("已生成最新本地备份：{}".format(backup_file), "success")
            return redirect(url_for("records_page"))

        flash("未知操作", "error")
        return redirect(url_for("import_page"))

    batches = list_batches(limit=12)
    detected_dates = []
    min_date = ""
    max_date = ""
    unknown_category_pairs = []
    if preview_data:
        detected_dates = _collect_detected_dates(preview_data["rows"])
        if detected_dates:
            min_date, max_date = detected_dates[0], detected_dates[-1]
        unknown_category_pairs = _unknown_category_pairs(preview_data["rows"])
    return render_template(
        "import.html",
        year=year,
        raw_text=raw_text,
        sample_loaded=False,
        batches=batches,
        preview_token=preview_token,
        preview_data=preview_data,
        detected_dates=detected_dates,
        min_date=min_date,
        max_date=max_date,
        unknown_category_pairs=unknown_category_pairs,
        required_columns=REQUIRED_COLUMNS,
        optional_columns=OPTIONAL_COLUMNS,
        consume_grouped=consume_grouped,
        income_grouped=income_grouped,
        consume_categories=category_options(False),
        income_categories=category_options(True),
    )


@app.route("/download/template.csv")
def download_template_csv():
    headers = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
    sample_rows = [
        ["2025-10-01", "34.22", "午餐", "支出", "工作日", "生活支出", "", "0", ""],
        ["2025-10-19", "4000", "工资入账", "收入", "月度工资", "工资", "", "0", ""],
        ["2025-10-22", "512", "轮渡", "支出", "国庆烟台返程", "交通", "生活支出", "1", "烟台国庆"],
    ]
    lines = [",".join(headers)]
    for row in sample_rows:
        vals = ['"{}"'.format(str(v).replace('"', '""')) for v in row]
        lines.append(",".join(vals))
    content = "\ufeff" + "\n".join(lines)

    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=import_template.csv"},
    )


@app.route("/download/template.xlsx")
def download_template_xlsx():
    from io import BytesIO
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "导入模板"
    headers = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
    ws.append(headers)
    ws.append(["2025-10-01", 34.22, "午餐", "支出", "工作日", "生活支出", "", 0, ""])
    ws.append(["2025-10-19", 4000, "工资入账", "收入", "月度工资", "工资", "", 0, ""])
    ws.append(["2025-10-22", 512, "轮渡", "支出", "国庆烟台返程", "交通", "生活支出", 1, "烟台国庆"])
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return Response(
        bio.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=import_template.xlsx"},
    )


@app.route("/staging/<int:batch_id>", methods=["GET", "POST"])
def staging_page(batch_id: int):
    ensure_db()
    batch = get_batch(batch_id)
    if not batch:
        flash("批次不存在", "error")
        return redirect(url_for("import_page"))

    action = request.form.get("action", "")
    if request.method == "POST":
        if action == "update_row":
            row_id = int(request.form["row_id"])
            payload = {
                "bill_date": request.form.get("bill_date") or None,
                "amount": request.form.get("amount", "0"),
                "detail": request.form.get("detail", ""),
                "note": request.form.get("note", ""),
                "direction": request.form.get("direction", "支出"),
                "category_l1": request.form.get("category_l1", ""),
                "category": request.form.get("category", "其他消费"),
                "is_travel": request.form.get("is_travel", "") == "1",
                "travel_tag": request.form.get("travel_tag", ""),
                "is_valid": request.form.get("is_valid", "") == "1",
                "error_msg": request.form.get("error_msg", ""),
            }
            update_staging_record(row_id, payload)
            flash("已更新临时记录", "success")
            return redirect(url_for("staging_page", batch_id=batch_id))

        if action == "delete_row":
            row_id = int(request.form["row_id"])
            delete_staging_record(row_id)
            flash("已删除临时记录", "success")
            return redirect(url_for("staging_page", batch_id=batch_id))

        if action == "bulk_delete_ids":
            ids = _parse_id_list(request.form.get("bulk_ids", ""))
            deleted = delete_staging_by_ids(batch_id, ids)
            flash("批量删除成功，共删除 {} 条".format(deleted), "success")
            return redirect(url_for("staging_page", batch_id=batch_id))

        if action == "bulk_delete_date":
            bill_date = request.form.get("bulk_date", "").strip()
            if not bill_date:
                flash("请先填写日期", "error")
            else:
                deleted = delete_staging_by_date(batch_id, bill_date)
                flash("按日期删除成功，共删除 {} 条".format(deleted), "success")
            return redirect(url_for("staging_page", batch_id=batch_id))

        if action == "confirm_batch":
            result = confirm_batch(batch_id)
            backup_file = write_latest_backup_csv()
            flash(
                "确认完成：新增 {} 条，覆盖删除旧记录 {} 条（按导入日期覆盖）".format(
                    result["inserted"], result["replaced_deleted"]
                ),
                "success",
            )
            if int(result.get("travel_reapplied", 0)) > 0:
                flash("已按旅游管理的日期打标规则回填旅游标签：{} 条".format(result["travel_reapplied"]), "success")
            flash("已生成最新本地备份：{}".format(backup_file), "success")
            return redirect(url_for("records_page"))

    rows = list_staging_records(batch_id)
    return render_template("staging.html", batch=batch, rows=rows)


@app.route("/records", methods=["GET", "POST"])
def records_page():
    ensure_db()
    action = request.form.get("action", "")
    if request.method == "POST":
        if action == "update":
            record_id = int(request.form["record_id"])
            cat_l2 = request.form.get("category", "其他消费")
            cat_l1_from_form = request.form.get("category_l1", "").strip()
            dir_ = request.form.get("direction", "支出")
            cat_l1 = cat_l1_from_form or l2_to_l1(cat_l2, dir_ == "收入") or cat_l2
            payload = {
                "bill_date": request.form["bill_date"],
                "amount": request.form.get("amount", "0"),
                "detail": request.form.get("detail", ""),
                "note": request.form.get("note", ""),
                "direction": dir_,
                "category_l1": cat_l1,
                "category": cat_l2,
                "is_travel": request.form.get("is_travel", "") == "1",
                "travel_tag": request.form.get("travel_tag", ""),
            }
            update_record(record_id, payload)
            flash("更新记录成功", "success")
            return _redirect_records_with_filters(request.form)
        if action == "bulk_delete_date":
            bill_date = request.form.get("bulk_date", "").strip()
            if not bill_date:
                flash("请先填写日期", "error")
            else:
                deleted = delete_records_by_date(bill_date)
                flash("按日期删除成功，共删除 {} 条".format(deleted), "success")
            return _redirect_records_with_filters(request.form)
        if action == "bulk_delete_range":
            start_date = request.form.get("bulk_start_date", "").strip()
            end_date = request.form.get("bulk_end_date", "").strip()
            if not start_date or not end_date:
                flash("请先选择删除日期范围", "error")
            else:
                deleted = delete_records_by_date_range(start_date, end_date)
                flash("按日期范围删除成功，共删除 {} 条".format(deleted), "success")
            return _redirect_records_with_filters(request.form)
        if action == "bulk_delete_dates":
            raw = request.form.get("bulk_dates", "").strip()
            dates = [x.strip() for x in raw.split(",") if x.strip()]
            deleted = delete_records_by_dates(dates)
            flash("按所选日期删除成功，共删除 {} 条".format(deleted), "success")
            return _redirect_records_with_filters(request.form)

    filters = {
        "year": request.args.get("year", ""),
        "month": request.args.get("month", ""),
        "direction": request.args.get("direction", ""),
        "category_l1": request.args.get("category_l1", ""),
        "category": request.args.get("category", ""),
        "is_travel": request.args.get("is_travel", ""),
        "keyword": request.args.get("keyword", "").strip(),
        "sort_by": request.args.get("sort_by", "bill_date"),
        "sort_order": request.args.get("sort_order", "desc"),
        "dates": [x.strip() for x in request.args.get("dates", "").split(",") if x.strip()],
    }
    has_any_filter = any(
        [
            filters["direction"],
            filters["category_l1"],
            filters["category"],
            filters["is_travel"],
            filters["keyword"],
            filters["dates"],
        ]
    )
    limit = None if has_any_filter else 20
    records = list_records(filters, limit=limit)
    category_values = sorted({str(r.get("category", "")) for r in records if str(r.get("category", "")).strip()})
    l1_values = sorted({str(r.get("category_l1", "")) for r in records if str(r.get("category_l1", "")).strip()})
    consume_grouped = category_options_grouped(False)
    income_grouped = category_options_grouped(True)
    return render_template(
        "records.html",
        records=records,
        filters=filters,
        category_values=category_values,
        l1_values=l1_values,
        consume_grouped=consume_grouped,
        income_grouped=income_grouped,
        is_default_limited=not has_any_filter,
        records_count=len(records),
        bill_dates_json=json.dumps(list_bill_dates(), ensure_ascii=False),
    )


@app.route("/analysis")
def analysis_page():
    ensure_db()
    years = list_available_years()
    selected_year = request.args.get("year", "")
    if selected_year.isdigit():
        y = int(selected_year)
    elif years:
        y = years[0]
    else:
        y = datetime.now().year

    metric = request.args.get("metric", "expense").strip().lower()
    if metric not in ("expense", "income"):
        metric = "expense"

    direction_filter = request.args.get("direction", "").strip()
    if direction_filter not in ("收入", "支出"):
        direction_filter = ""
    category_filters = [x.strip() for x in request.args.getlist("category") if x.strip()]

    heatmap_rows = daily_heatmap_data(y)
    heatmap_map = {}
    max_val = 0.0
    annual_total = 0.0
    month_total_map = {}
    for r in heatmap_rows:
        day = str(r.get("bill_date"))
        val = float(r.get(metric, 0.0))
        heatmap_map[day] = val
        annual_total += val
        month_key = day[:7] if len(day) >= 7 else ""
        if month_key:
            month_total_map[month_key] = month_total_map.get(month_key, 0.0) + val
        if val > max_val:
            max_val = val

    summary_rows = summary_by_category_month(y, direction_filter, category_filters)
    category_options_all = list_categories(y, direction_filter)
    consume_grouped = category_options_grouped(False)
    income_grouped = category_options_grouped(True)
    if direction_filter == "支出":
        analysis_grouped = consume_grouped
    elif direction_filter == "收入":
        analysis_grouped = income_grouped
    else:
        # 方向=全部时，合并展示；同名一级类型下做并集
        merged: dict = {}
        for g in consume_grouped + income_grouped:
            l1 = g.get("l1", "")
            merged.setdefault(l1, set()).update(g.get("l2s", []))
        analysis_grouped = [{"l1": k, "l2s": sorted(list(v))} for k, v in sorted(merged.items(), key=lambda x: x[0])]

    return render_template(
        "analysis.html",
        years=years,
        selected_year=y,
        metric=metric,
        annual_total=round(annual_total, 2),
        month_total_map_json=json.dumps(month_total_map, ensure_ascii=False),
        heatmap_map_json=json.dumps(heatmap_map, ensure_ascii=False),
        heatmap_max=max_val,
        summary_rows=summary_rows,
        show_category_dim=bool(category_filters),
        direction_filter=direction_filter,
        category_filters=category_filters,
        category_options=category_options_all,
        category_grouped=analysis_grouped,
    )


@app.route("/types", methods=["GET", "POST"])
def types_page():
    ensure_db()
    if request.method == "POST":
        action = request.form.get("action", "")
        target = request.form.get("target", "consume")
        is_income = target == "income"
        l1 = request.form.get("l1", "").strip()
        l2 = request.form.get("l2", "").strip()
        pattern = request.form.get("pattern", "").strip()
        if action in ("add", "update"):
            if not l1 or not l2:
                flash("一级类型和二级类型名不能为空", "error")
            else:
                upsert_rule(l1, l2, pattern, is_income)
                flash("已保存类型规则", "success")
            return redirect(url_for("types_page"))
        if action == "delete":
            delete_rule(l1, l2, is_income)
            flash("已删除类型规则", "success")
            return redirect(url_for("types_page"))

    return render_template(
        "types.html",
        consume_rows=list_rule_rows(False),
        income_rows=list_rule_rows(True),
    )


@app.route("/travel", methods=["GET", "POST"])
def travel_page():
    ensure_db()
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "update_trip_companions":
            tag = request.form.get("trip_tag", "").strip()
            companions = request.form.get("trip_companions", "").strip()
            if not tag:
                flash("行程标签不能为空", "error")
                return redirect(url_for("travel_page"))
            count = update_travel_companions_by_trip_tag(tag, companions)
            flash("已更新同行人，影响 {} 条记录".format(count), "success")
            return redirect(url_for("travel_page"))

        raw = request.form.get("dates", "").strip()
        dates = [x.strip() for x in raw.split(",") if x.strip()]
        if not dates:
            flash("请先选择日期", "error")
            return redirect(url_for("travel_page"))
        if action == "set_tag":
            tag = request.form.get("travel_tag", "").strip()
            companions = request.form.get("travel_companions", "").strip()
            if not tag:
                flash("旅游标签不能为空", "error")
                return redirect(url_for("travel_page"))
            count = set_travel_tag_by_dates(dates, tag, companions)
            flash("旅游打标完成，更新 {} 条记录".format(count), "success")
            return redirect(url_for("travel_page"))
        if action == "clear_tag":
            count = clear_travel_tag_by_dates(dates)
            flash("已清除旅游标签，更新 {} 条记录".format(count), "success")
            return redirect(url_for("travel_page"))

    travel = travel_summary()
    tagged_rows = travel_tagged_dates(limit=365)
    return render_template(
        "travel.html",
        travel=travel,
        tagged_rows=tagged_rows,
        bill_dates_json=json.dumps(list_bill_dates(), ensure_ascii=False),
    )


@app.route("/download/offline_report.zip")
def download_offline_report_zip():
    ensure_db()
    from io import BytesIO
    import zipfile

    payload = collect_payload()
    html = render_report_html(payload)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("report.html", html)
        z.writestr("data.json", json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    bio.seek(0)
    return Response(
        bio.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename=offline_report_{ts}.zip"},
    )


if __name__ == "__main__":
    ensure_db()
    port = int(os.environ.get("PORT", "8501"))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=False, use_reloader=False)
