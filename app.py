from pathlib import Path
from collections import OrderedDict
import hashlib
import json
import os
import re
import secrets
import sys
from datetime import datetime, timedelta

from flask import Flask, redirect, render_template, request, url_for, flash
from flask import Response, session, jsonify, send_from_directory, abort, g

BASE_DIR = Path(__file__).resolve().parent
# 模块路径：账单 / 诗词包内仍用短导入名（db / poem_admin …）
for _mod in ("modules/bills", "modules/poems", "modules/water"):
    _p = str(BASE_DIR / _mod.replace("/", os.sep))
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auth import (
    auth_bp,
    auth_enabled,
    guest_can_access,
    has_site_access,
    is_guest,
    is_logged_in,
    is_owner,
)
from db.backup import (
    create_backup_bundle,
    find_latest_main_csv,
    get_backup_dir,
    list_backup_bundle_files,
)
from offline_report import collect_payload, render_report_html
from db.repository import (
    backfill_category_l1,
    collapse_categories_to_single_level,
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
    list_journal_records,
    list_l1_categories,
    list_records,
    list_staging_records,
    summary_by_category_month,
    set_travel_tag_by_date_range,
    clear_travel_tag_by_date_range,
    set_travel_tag_by_dates,
    clear_travel_tag_by_dates,
    batch_update_travel_companions,
    travel_summary,
    update_staging_record,
    update_record,
)
from db.schema import init_db
from importers import OPTIONAL_COLUMNS, REQUIRED_COLUMNS, parse_input_to_staging
from parser import ImportOptions
from poem_admin import delete_poem, get_poem, load_poems, pick_poem_for_date, sort_poems_desc, upsert_poem
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
    peek_legacy_l2_map,
    save_rules,
    RULE_FILE,
)
import json as _json_for_rules


ZERO_AMOUNT_CATEGORY = "零金额"


def _is_zero_amount(amount) -> bool:
    try:
        return abs(float(amount or 0)) < 1e-9
    except Exception:
        return False


def _uses_remote_data_dir() -> bool:
    """Fly 等远程 Volume：备份在服务器上，需同步到本机绑定目录。"""
    return bool((os.environ.get("BILL_DATA_DIR") or "").strip())


def _backup_zip_bytes(clear_old: bool = True) -> Response:
    """强制下载 zip（未绑定本机文件夹时的回退）。"""
    from io import BytesIO
    import zipfile

    main_csv, files = create_backup_bundle(clear_old=clear_old)
    ts = Path(main_csv).stem.replace("records_backup_", "", 1)
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for fp in files:
            z.write(fp, arcname=Path(fp).name)
    bio.seek(0)
    return Response(
        bio.getvalue(),
        mimetype="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=records_backup_{ts}.zip",
        },
    )


def _backup_and_redirect(endpoint: str, **url_kwargs):
    """
    写入服务器 backup/ 后跳转：
    - 本机运行：已直接落在项目 backup/，无需再下载
    - 正式站：标记 session，由前端写入用户绑定的本机 backup 文件夹
    """
    main_csv, _files = create_backup_bundle(clear_old=True)
    backup_dir = get_backup_dir()
    if not _uses_remote_data_dir():
        flash("已直接写入本机项目目录：{}".format(backup_dir), "success")
        return redirect(url_for(endpoint, **url_kwargs))
    session["sync_local_backup"] = True
    flash(
        "服务器已备份（{}）。若已绑定本机 backup 文件夹将自动写入；否则请侧栏绑定，或下载 zip。".format(
            Path(main_csv).name
        ),
        "success",
    )
    return redirect(url_for(endpoint, **url_kwargs))




def _load_dotenv() -> None:
    """读取项目根目录 .env（不覆盖已有环境变量）。"""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = value.strip().strip('"').strip("'")
    except OSError:
        return


_load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("BILL_SECRET_KEY") or os.environ.get("SECRET_KEY") or "bill-dev-secret-change-me"
app.permanent_session_lifetime = timedelta(days=14)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# 公网 HTTPS 部署时设 BILL_COOKIE_SECURE=1，本机 HTTP 调试不要开
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("BILL_COOKIE_SECURE", "").strip() in ("1", "true", "yes")
app.register_blueprint(auth_bp)

from modules.water import water_bp
from modules.notes import notes_bp

app.register_blueprint(water_bp)
app.register_blueprint(notes_bp)

TOOLS_DIR = BASE_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

SAMPLE_PATH = BASE_DIR / "tools" / "Transfer Dock_Text_20260318112028.txt"
if not SAMPLE_PATH.exists():
    SAMPLE_PATH = BASE_DIR / "1.待规则化年份账单" / "2025账单.txt"
db_ready = False


@app.before_request
def _require_access():
    endpoint = request.endpoint
    if endpoint and (
        endpoint.startswith("auth.")
        or endpoint == "static"
    ):
        return None

    # 未选角色 → 入口
    if not has_site_access():
        return redirect(url_for("auth.login", next=request.path))

    # 游客白名单
    if is_guest():
        if guest_can_access(endpoint):
            return None
        flash("游客模式仅可查看诗词与笔记专栏", "error")
        return redirect(url_for("poems_page"))

    # 所有者放行
    return None


@app.before_request
def _consume_local_backup_sync_flag():
    endpoint = request.endpoint
    if not endpoint or endpoint == "static" or endpoint.startswith("auth."):
        g.sync_local_backup = False
        return
    # 每请求只取一次，避免静态资源请求抢走标记
    g.sync_local_backup = bool(session.pop("sync_local_backup", False))


@app.context_processor
def _inject_auth():
    return {
        "auth_enabled": auth_enabled(),
        "is_logged_in": is_logged_in(),
        "is_owner": is_owner(),
        "is_guest": is_guest(),
        "access_role": "guest" if is_guest() else ("owner" if is_owner() else None),
        "sync_local_backup": bool(getattr(g, "sync_local_backup", False)),
    }



def ensure_db():
    global db_ready
    if not db_ready:
        init_db()
        _migrate_l1()
        _migrate_single_level_categories()
        try:
            from modules.notes.store import init_notes_db

            init_notes_db()
        except Exception:
            pass
        db_ready = True


def _migrate_l1():
    """兼容：为空的 category_l1 按旧二级名回填（单层迁移前可能仍有用）。"""
    try:
        legacy = peek_legacy_l2_map()
        if legacy:
            backfill_category_l1(legacy)
    except Exception:
        pass


def _migrate_single_level_categories():
    """一次性：规则扁平化 + 记录折叠为仅一级类型。"""
    try:
        data_dir = Path(os.environ.get("BILL_DATA_DIR") or (BASE_DIR / "data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        marker = data_dir / ".category_single_level_v1"
        if marker.exists():
            return
        legacy = {}
        if os.path.exists(RULE_FILE):
            with open(RULE_FILE, "r", encoding="utf-8") as f:
                raw = _json_for_rules.load(f)
            from rule_manager import _normalize_rules

            rules, legacy = _normalize_rules(raw)
            save_rules(rules)
        else:
            save_rules(load_rules())
        collapse_categories_to_single_level(legacy)
        marker.write_text("ok\n", encoding="utf-8")
    except Exception:
        pass


def _journal_groups(rows):
    groups = OrderedDict()
    for row in rows:
        day = str(row.get("bill_date") or "")
        if not day:
            continue
        bucket = groups.setdefault(
            day,
            {
                "bill_date": day,
                "records": [],
                "notes": [],
                "expense_total": 0.0,
                "income_total": 0.0,
            },
        )
        bucket["records"].append(row)
        note = str(row.get("note") or "").strip()
        if note and note not in bucket["notes"]:
            bucket["notes"].append(note)
        amount = float(row.get("amount") or 0)
        if str(row.get("direction") or "") == "收入":
            bucket["income_total"] += amount
        else:
            bucket["expense_total"] += amount

    out = list(groups.values())
    for group in out:
        group["record_count"] = len(group["records"])
        group["note_count"] = len(group["notes"])
        group["expense_total"] = round(group["expense_total"], 2)
        group["income_total"] = round(group["income_total"], 2)
    return out


def _poem_form_payload(src=None):
    src = src or {}
    story = src.get("story") or {}
    return {
        "poem_date": str(src.get("poem_date") or "").strip(),
        "content": str(src.get("content") or "").strip(),
        "source": str(story.get("source") or "").strip(),
        "full_poem": str(story.get("full_poem") or "").strip(),
        "background": str(story.get("background") or "").strip(),
        "life_state": str(story.get("life_state") or "").strip(),
        "poem_mood": str(story.get("poem_mood") or "").strip(),
        "why_write": str(story.get("why_write") or "").strip(),
        "interpretation": str(story.get("interpretation") or "").strip(),
        "meaning": str(story.get("meaning") or "").strip(),
    }


def _poem_payload_from_form():
    return {
        "poem_date": (request.form.get("poem_date") or "").strip(),
        "content": (request.form.get("content") or "").strip(),
        "story": {
            "source": (request.form.get("source") or "").strip(),
            "full_poem": (request.form.get("full_poem") or "").strip(),
            "background": (request.form.get("background") or "").strip(),
            "life_state": (request.form.get("life_state") or "").strip(),
            "poem_mood": (request.form.get("poem_mood") or "").strip(),
            "why_write": (request.form.get("why_write") or "").strip(),
            "interpretation": (request.form.get("interpretation") or "").strip(),
            "meaning": (request.form.get("meaning") or "").strip(),
        },
    }


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
        if _is_zero_amount(r.get("amount")):
            continue
        d = str(r.get("direction", "")).strip()
        if d not in ("收入", "支出"):
            continue
        is_income = d == "收入"
        cat = str(r.get("category") or "").strip()
        raw = str(r.get("explicit_category_raw") or cat or "").strip()
        # 即使历史预览当时是“已知”，但用户后续编辑了字典（删除/改名），也要重新判定未知并提示映射
        cu = bool(r.get("category_unknown"))
        if cat and cat not in ("待分类", "待分类收入", ZERO_AMOUNT_CATEGORY):
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
        # 金额为 0：不需要分类，不进待分类 / 待映射
        if _is_zero_amount(amount):
            category = cat_l1 = ZERO_AMOUNT_CATEGORY
            cu = False
            explicit_raw = ""
        elif is_known_category(category, is_income) or is_known_l1(category, is_income):
            cu = False
            explicit_raw = ""
            category = l2_to_l1(category, is_income) or category
            cat_l1 = category
        elif is_known_l1(cat_l1, is_income) or is_known_category(cat_l1, is_income):
            cu = False
            explicit_raw = ""
            category = cat_l1 = (l2_to_l1(cat_l1, is_income) or cat_l1)
        elif cu and not explicit_raw:
            explicit_raw = category
        else:
            # 双写对齐
            if not cat_l1:
                cat_l1 = category
            elif not category:
                category = cat_l1
        # 业务规则：导入清洗阶段不维护旅游字段，统一由“旅游管理”页面按日期维护
        is_travel = False
        travel_tag = ""
        errors = []
        if not bill_date:
            errors.append("日期格式错误")
        # 纯日记天：金额为 0 + 有日记 + 无消费明细 → 仍有效，须入库供生活日志使用
        if detail == "":
            if note and _is_zero_amount(amount):
                detail = "日记"
                category = cat_l1 = ZERO_AMOUNT_CATEGORY
            else:
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
                # 支持映射 token: 纯类型名 或 L1::类型名（兼容旧 L2::）
                mapped = ""
                if target.startswith("L1::") or target.startswith("L2::"):
                    mapped = target[4:].strip()
                else:
                    mapped = target
                if not mapped or not (
                    is_known_category(mapped, is_income) or is_known_l1(mapped, is_income)
                ):
                    # 尝试旧二级名映射
                    mapped2 = l2_to_l1(mapped, is_income) if mapped else ""
                    if not mapped2 or not is_known_category(mapped2, is_income):
                        continue
                    mapped = mapped2
                else:
                    mapped = l2_to_l1(mapped, is_income) or mapped
                r["category"] = mapped
                r["category_l1"] = mapped
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
            if any((r.get("category_unknown") and not _is_zero_amount(r.get("amount"))) for r in rows):
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
            return _backup_and_redirect("import_page")

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
            cat = (request.form.get("category") or request.form.get("category_l1") or "其他消费").strip()
            payload = {
                "bill_date": request.form.get("bill_date") or None,
                "amount": request.form.get("amount", "0"),
                "detail": request.form.get("detail", ""),
                "note": request.form.get("note", ""),
                "direction": request.form.get("direction", "支出"),
                "category_l1": cat,
                "category": cat,
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
            flash(
                "确认完成：新增 {} 条，覆盖删除旧记录 {} 条（按导入日期覆盖）".format(
                    result["inserted"], result["replaced_deleted"]
                ),
                "success",
            )
            if int(result.get("travel_reapplied", 0)) > 0:
                flash("已按旅游管理的日期打标规则回填旅游标签：{} 条".format(result["travel_reapplied"]), "success")
            return _backup_and_redirect("records_page")

    rows = list_staging_records(batch_id)
    return render_template(
        "staging.html",
        batch=batch,
        rows=rows,
        consume_grouped=category_options_grouped(False),
        income_grouped=category_options_grouped(True),
    )


@app.route("/records", methods=["GET", "POST"])
def records_page():
    ensure_db()
    action = request.form.get("action", "")
    if request.method == "POST":
        if action == "update":
            record_id = int(request.form["record_id"])
            cat = (request.form.get("category") or request.form.get("category_l1") or "其他消费").strip()
            dir_ = request.form.get("direction", "支出")
            payload = {
                "bill_date": request.form["bill_date"],
                "amount": request.form.get("amount", "0"),
                "detail": request.form.get("detail", ""),
                "note": request.form.get("note", ""),
                "direction": dir_,
                "category_l1": cat,
                "category": cat,
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


@app.route("/journal")
def journal_page():
    ensure_db()
    month = request.args.get("month", "").strip()
    keyword = request.args.get("keyword", "").strip()
    focus_date = request.args.get("date", "").strip()
    from_source = request.args.get("from", "").strip()
    back_year = request.args.get("year", "").strip()
    back_metric = request.args.get("metric", "expense").strip().lower()
    if back_metric not in ("expense", "income"):
        back_metric = "expense"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", focus_date or ""):
        focus_date = ""

    # 从分析看板点进来时，默认收窄到该月，方便定位当天
    if focus_date and not month and not keyword:
        month = focus_date[:7]

    rows = list_journal_records(month=month, keyword=keyword)
    groups = _journal_groups(rows)

    if focus_date and not any(g["bill_date"] == focus_date for g in groups):
        day_rows = list_records({"dates": [focus_date]}, limit=None)
        if day_rows:
            extra = _journal_groups(day_rows)
        else:
            extra = [
                {
                    "bill_date": focus_date,
                    "records": [],
                    "notes": [],
                    "expense_total": 0.0,
                    "income_total": 0.0,
                    "record_count": 0,
                    "note_count": 0,
                }
            ]
        by_day = {g["bill_date"]: g for g in groups}
        for g in extra:
            by_day[g["bill_date"]] = g
        groups = sorted(by_day.values(), key=lambda g: g["bill_date"], reverse=True)

    all_months = sorted({str(r.get("bill_date") or "")[:7] for r in rows if str(r.get("bill_date") or "")[:7]}, reverse=True)
    if focus_date and focus_date[:7] not in all_months:
        all_months = sorted(set(all_months) | {focus_date[:7]}, reverse=True)

    total_expense = round(sum(float(g["expense_total"]) for g in groups), 2)
    total_income = round(sum(float(g["income_total"]) for g in groups), 2)
    note_count = sum(int(g["note_count"]) for g in groups)
    latest_day = groups[0]["bill_date"] if groups else ""
    back_to_analysis = from_source == "analysis"
    return render_template(
        "journal.html",
        filters={"month": month, "keyword": keyword},
        groups=groups,
        all_months=all_months,
        total_days=len(groups),
        total_notes=note_count,
        total_expense=total_expense,
        total_income=total_income,
        latest_day=latest_day,
        focus_date=focus_date,
        back_to_analysis=back_to_analysis,
        back_year=back_year,
        back_metric=back_metric,
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
        name = (request.form.get("name") or request.form.get("l1") or "").strip()
        # 兼容旧表单字段
        if not name:
            name = (request.form.get("l2") or "").strip()
        pattern = request.form.get("pattern", "").strip()
        if action in ("add", "update"):
            if not name:
                flash("类型名不能为空", "error")
                return redirect(url_for("types_page"))
            upsert_rule(name, pattern, is_income)
            flash("已保存类型规则", "success")
            return _backup_and_redirect("types_page")
        if action == "delete":
            delete_rule(name, is_income)
            flash("已删除类型规则", "success")
            return _backup_and_redirect("types_page")

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
        if action == "batch_update_companions":
            try:
                items = json.loads(request.form.get("companions_json") or "[]")
            except Exception:
                flash("同行人数据格式错误", "error")
                return redirect(url_for("travel_page"))
            if not isinstance(items, list):
                flash("同行人数据格式错误", "error")
                return redirect(url_for("travel_page"))
            # 仅提交有变更的行程
            changed = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                tag = str(it.get("tag") or "").strip()
                if not tag:
                    continue
                new_c = str(it.get("companions") or "").strip()
                old_c = str(it.get("original") or "").strip()
                if new_c == old_c:
                    continue
                changed.append({"tag": tag, "companions": new_c})
            if not changed:
                flash("同行人无变更", "success")
                return redirect(url_for("travel_page"))
            result = batch_update_travel_companions(changed)
            flash(
                "已批量更新同行人：{} 个行程，影响 {} 条账单".format(
                    result["trips"], result["records"]
                ),
                "success",
            )
            return _backup_and_redirect("travel_page")

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
            return _backup_and_redirect("travel_page")
        if action == "clear_tag":
            count = clear_travel_tag_by_dates(dates)
            flash("已清除旅游标签，更新 {} 条记录".format(count), "success")
            return _backup_and_redirect("travel_page")

    travel = travel_summary()
    return render_template(
        "travel.html",
        travel=travel,
        trips_json=json.dumps(travel.get("by_trip") or [], ensure_ascii=False, default=str),
        bill_dates_json=json.dumps(list_bill_dates(), ensure_ascii=False),
    )


def _poem_admin_password() -> str:
    return (os.environ.get("POEM_ADMIN_PASSWORD") or os.environ.get("BILL_ACCESS_PASSWORD") or "").strip()


def _is_poem_admin() -> bool:
    if not _poem_admin_password():
        return True
    return bool(session.get("poem_admin_ok"))


def _require_poem_admin():
    """未通过维护密码时跳到维护入口。返回 None 表示已放行。"""
    if _is_poem_admin():
        return None
    flash("请输入维护密码后再管理诗库", "error")
    return redirect(url_for("poem_admin_page"))


@app.route("/poems")
def poems_page():
    ensure_db()
    keyword = request.args.get("keyword", "").strip()
    month = request.args.get("month", "").strip()
    all_poems = load_poems()
    poems = all_poems
    if keyword:
        low = keyword.lower()
        poems = [p for p in poems if low in str(p.get("content", "")).lower() or low in json.dumps(p.get("story") or {}, ensure_ascii=False).lower()]
    if month:
        poems = [p for p in poems if str(p.get("poem_date") or "").startswith(month)]
    poems = sort_poems_desc(poems)
    all_months = sorted({str(p.get("poem_date") or "")[:7] for p in all_poems if str(p.get("poem_date") or "")[:7]}, reverse=True)
    today_poem = pick_poem_for_date(datetime.now().strftime("%Y-%m-%d"), all_poems)
    return render_template(
        "poems.html",
        poems=poems,
        today_poem=today_poem,
        today_label="{} 年 {} 月 {} 日".format(datetime.now().year, datetime.now().month, datetime.now().day),
        filters={"keyword": keyword, "month": month},
        all_months=all_months,
        poem_total=len(all_poems),
        is_poem_admin=_is_poem_admin(),
    )


@app.route("/poems/admin", methods=["GET", "POST"])
def poem_admin_page():
    ensure_db()
    if request.method == "POST" and not _is_poem_admin():
        pwd = (request.form.get("password") or "").strip()
        if pwd and secrets.compare_digest(
            hashlib.sha256(pwd.encode("utf-8")).digest(),
            hashlib.sha256(_poem_admin_password().encode("utf-8")).digest(),
        ):
            session["poem_admin_ok"] = True
            session.permanent = True
            flash("已进入诗库维护模式", "success")
            return redirect(url_for("poem_admin_page"))
        flash("维护密码错误", "error")
        return redirect(url_for("poem_admin_page"))

    if not _is_poem_admin():
        return render_template("poem_admin.html", is_admin=False, poems=[])

    poems = sort_poems_desc(load_poems())
    return render_template("poem_admin.html", is_admin=True, poems=poems)


@app.route("/poems/admin/logout")
def poem_admin_logout():
    session.pop("poem_admin_ok", None)
    flash("已退出诗库维护模式", "success")
    return redirect(url_for("poems_page"))


@app.route("/poems/new", methods=["GET", "POST"])
def poem_create_page():
    ensure_db()
    guard = _require_poem_admin()
    if guard:
        return guard
    return render_template("poem_create_hub.html")


@app.route("/poems/new/form", methods=["GET", "POST"])
def poem_create_form_page():
    ensure_db()
    guard = _require_poem_admin()
    if guard:
        return guard
    form = _poem_form_payload({"poem_date": datetime.now().strftime("%Y-%m-%d")})
    if request.method == "POST":
        form = _poem_form_payload(_poem_payload_from_form())
        if not form["poem_date"] or not form["content"]:
            flash("日期和诗句内容不能为空", "error")
        else:
            poem_id = upsert_poem(None, _poem_payload_from_form())
            flash("已新增诗词，并同步更新诗库页面", "success")
            return redirect(url_for("poem_edit_page", poem_id=poem_id))
    return render_template("poem_edit.html", form=form, poem_id=None)


def _session_recommend_batch() -> list:
    from poem_intake import load_intake_batch

    key = session.get("poem_recommend_batch_id") or ""
    raw = load_intake_batch(key) if key else []
    return raw if isinstance(raw, list) else []


def _set_recommend_batch(items: list) -> None:
    from poem_intake import save_intake_batch

    key = save_intake_batch(items, key=session.get("poem_recommend_batch_id") or None)
    session["poem_recommend_batch_id"] = key
    session.pop("poem_recommend_batch", None)


@app.route("/poems/new/recommend", methods=["GET", "POST"])
def poem_recommend_page():
    ensure_db()
    guard = _require_poem_admin()
    if guard:
        return guard

    from poem_intake import default_poem_date, existing_contents, recommend_poems, style_profile

    poems = load_poems()
    profile = style_profile(poems)
    batch = _session_recommend_batch()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "refresh":
            try:
                batch = recommend_poems(poems, count=5, use_llm=True)
                _set_recommend_batch(batch)
                flash("已按当前诗库风格推荐 {} 句".format(len(batch)), "success")
            except Exception as exc:
                flash("推荐失败：{}".format(exc), "error")
            return redirect(url_for("poem_recommend_page"))

        idx_raw = (request.form.get("idx") or "").strip()
        idx = int(idx_raw) if idx_raw.isdigit() else -1
        if idx < 0 or idx >= len(batch):
            flash("候选已失效，请重新推荐", "error")
            return redirect(url_for("poem_recommend_page"))

        if action == "dismiss":
            batch.pop(idx)
            _set_recommend_batch(batch)
            flash("已跳过该句", "success")
            return redirect(url_for("poem_recommend_page"))

        if action == "accept":
            item = batch[idx]
            content = str(item.get("content") or "").strip()
            if content in existing_contents(poems):
                flash("诗库中已有这句，未重复添加", "error")
                batch.pop(idx)
                _set_recommend_batch(batch)
                return redirect(url_for("poem_recommend_page"))
            poem_date = (request.form.get("poem_date") or default_poem_date()).strip()
            try:
                poem_id = upsert_poem(
                    None,
                    {
                        "poem_date": poem_date,
                        "content": content,
                        "story": item.get("story") or {},
                    },
                )
                batch.pop(idx)
                _set_recommend_batch(batch)
                flash("已加入诗库 #{}".format(poem_id), "success")
            except Exception as exc:
                flash("加入失败：{}".format(exc), "error")
            return redirect(url_for("poem_recommend_page"))

    return render_template(
        "poem_recommend.html",
        recommendations=batch,
        style_tags=profile.get("top_tags") or [],
        default_date=default_poem_date(),
    )


@app.route("/poems/new/lookup", methods=["GET", "POST"])
def poem_lookup_page():
    ensure_db()
    guard = _require_poem_admin()
    if guard:
        return guard

    from poem_intake import (
        clear_intake_item,
        default_poem_date,
        existing_contents,
        load_intake_item,
        lookup_poem_line,
        save_intake_item,
    )

    preview_id = session.get("poem_lookup_preview_id")
    preview = load_intake_item(preview_id) if preview_id else None
    query_content = ""

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "query":
            query_content = (request.form.get("content") or "").strip()
            result = lookup_poem_line(query_content, use_llm=True)
            if not result.get("ok"):
                flash(result.get("error") or "查询失败", "error")
                clear_intake_item(session.pop("poem_lookup_preview_id", None))
                return redirect(url_for("poem_lookup_page"))
            item_id = save_intake_item(
                {
                    "content": result.get("content") or query_content,
                    "verified": bool(result.get("verified")),
                    "match_score": int(result.get("match_score") or 0),
                    "source": result.get("source") or "",
                    "authenticity": result.get("authenticity") or "",
                    "story": result.get("story") or {},
                }
            )
            session["poem_lookup_preview_id"] = item_id
            session.pop("poem_lookup_preview", None)
            flash("已生成诗境预览，请品读后决定是否加入", "success")
            return redirect(url_for("poem_lookup_page"))

        if action == "accept":
            preview = load_intake_item(session.get("poem_lookup_preview_id")) or {}
            content = str(preview.get("content") or "").strip()
            if not content:
                flash("没有可加入的预览结果，请先查询", "error")
                return redirect(url_for("poem_lookup_page"))
            if content in existing_contents(load_poems()):
                flash("诗库中已有这句，未重复添加", "error")
                return redirect(url_for("poem_lookup_page"))
            poem_date = (request.form.get("poem_date") or default_poem_date()).strip()
            try:
                poem_id = upsert_poem(
                    None,
                    {
                        "poem_date": poem_date,
                        "content": content,
                        "story": preview.get("story") or {},
                    },
                )
                clear_intake_item(session.pop("poem_lookup_preview_id", None))
                flash("已加入诗库 #{}".format(poem_id), "success")
                return redirect(url_for("poem_edit_page", poem_id=poem_id))
            except Exception as exc:
                flash("加入失败：{}".format(exc), "error")
                return redirect(url_for("poem_lookup_page"))

        if action == "clear":
            clear_intake_item(session.pop("poem_lookup_preview_id", None))
            flash("已清空查询结果", "success")
            return redirect(url_for("poem_lookup_page"))

    return render_template(
        "poem_lookup.html",
        preview=preview if isinstance(preview, dict) else None,
        query_content=query_content or ((preview or {}).get("content") if isinstance(preview, dict) else ""),
        default_date=default_poem_date(),
    )


@app.route("/poems/<int:poem_id>/edit", methods=["GET", "POST"])
def poem_edit_page(poem_id: int):
    ensure_db()
    guard = _require_poem_admin()
    if guard:
        return guard
    poem = get_poem(poem_id)
    if not poem:
        flash("这条诗词不存在或已被删除", "error")
        return redirect(url_for("poem_admin_page"))
    form = _poem_form_payload(poem)
    if request.method == "POST":
        form = _poem_form_payload(_poem_payload_from_form())
        if not form["poem_date"] or not form["content"]:
            flash("日期和诗句内容不能为空", "error")
        else:
            new_id = upsert_poem(poem_id, _poem_payload_from_form())
            flash("已保存诗词，并重建展示页", "success")
            return redirect(url_for("poem_edit_page", poem_id=new_id))
    return render_template("poem_edit.html", form=form, poem_id=poem_id)


@app.route("/poems/<int:poem_id>/delete", methods=["POST"])
def poem_delete_page(poem_id: int):
    ensure_db()
    guard = _require_poem_admin()
    if guard:
        return guard
    if delete_poem(poem_id):
        flash("已删除诗词，并同步重建诗库", "success")
    else:
        flash("未找到要删除的诗词", "error")
    return redirect(url_for("poem_admin_page"))


@app.route("/api/backup/latest")
def api_backup_latest():
    if not is_owner():
        return jsonify({"error": "forbidden"}), 403
    ensure_db()
    main_csv = find_latest_main_csv()
    if not main_csv:
        return jsonify({"files": []})
    files = []
    for fp in list_backup_bundle_files(main_csv):
        name = Path(fp).name
        files.append({"name": name, "url": url_for("api_backup_file", name=name)})
    return jsonify({"files": files, "main": Path(main_csv).name})


@app.route("/api/backup/file/<name>")
def api_backup_file(name: str):
    if not is_owner():
        abort(403)
    if not re.fullmatch(r"records_backup_[A-Za-z0-9_.-]+", name or ""):
        abort(400)
    backup_dir = get_backup_dir()
    path = Path(backup_dir) / name
    if not path.is_file():
        abort(404)
    return send_from_directory(backup_dir, name, as_attachment=False)


@app.route("/download/backup.zip")
def download_backup_zip():
    """生成备份：默认走本机绑定同步；?raw=1 强制下载 zip。"""
    ensure_db()
    if request.args.get("raw") == "1":
        flash("已生成 zip，请解压到本机项目的 backup/ 文件夹。", "success")
        return _backup_zip_bytes(clear_old=True)
    return _backup_and_redirect("records_page")


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
