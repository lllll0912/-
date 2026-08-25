"""健康档案：本地 catalog + 附件。"""

from __future__ import annotations

import calendar as cal_mod
import json
import os
import re
from collections import OrderedDict
from datetime import date
from pathlib import Path
from typing import Any, Optional

RESULT_UNKNOWN = "unknown"
RESULT_NORMAL = "normal"
RESULT_ABNORMAL = "abnormal"
RESULT_STATUSES = (RESULT_UNKNOWN, RESULT_NORMAL, RESULT_ABNORMAL)


def bundled_health_root() -> Path:
    """仓库/镜像内的医疗数据（含检验单原件）。正式站从这里读图，不进 Fly Volume。"""
    return Path(__file__).resolve().parents[1] / "数据"


def data_write_root() -> Path:
    """
    新上传落盘目录（相对路径与 Git 一致）。
    - 本机：医疗/数据/（直接进仓库，再 git push）
    - Fly：/data/health/（临时缓存立刻可看；同时尽量 commit 进 GitHub）
    """
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / "health"
    return bundled_health_root()


def meta_root() -> Path:
    """
    可写元数据（catalog / 目的标注）。
    - 本机：直接写 医疗/数据/_meta（进 Git）
    - Fly：Volume 上 /data/health/_meta
    """
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / "health" / "_meta"
    return bundled_health_root() / "_meta"


def health_root() -> Path:
    return bundled_health_root()


def _bundled_meta_file(name: str) -> Path:
    return bundled_health_root() / "_meta" / name


def load_doc_categories() -> list[dict[str, Any]]:
    for path in (meta_root() / "categories.json", _bundled_meta_file("categories.json")):
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return list(data.get("categories") or [])
    return [
        {"id": "lab", "label": "检验单", "folder": "01_本人_检验单", "upload": True},
        {"id": "outpatient", "label": "门诊单", "folder": "05_本人_门诊单", "upload": True},
        {"id": "medication", "label": "用药", "folder": "06_本人_用药", "upload": True},
    ]


def category_label(category_id: str) -> str:
    cid = (category_id or "").strip()
    for c in load_doc_categories():
        if c.get("id") == cid:
            return str(c.get("label") or cid)
    return cid or "未分类"


def category_folder(category_id: str) -> str:
    cid = (category_id or "lab").strip() or "lab"
    for c in load_doc_categories():
        if c.get("id") == cid:
            return str(c.get("folder") or "01_本人_检验单")
    return "01_本人_检验单"


def catalog_path() -> Path:
    """优先用 Volume 里已有标注的 catalog；否则用镜像自带的（含 2024/2025 全部记录）。"""
    writable = meta_root() / "catalog.json"
    bundled = _bundled_meta_file("catalog.json")
    if writable.is_file():
        try:
            data = json.loads(writable.read_text(encoding="utf-8"))
            if data.get("records"):
                return writable
        except Exception:
            pass
    if bundled.is_file():
        return bundled
    return writable


def load_catalog() -> dict[str, Any]:
    path = catalog_path()
    if not path.is_file():
        return {
            "version": 2,
            "records": [],
            "stats": {},
            "purpose_tags": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_catalog(catalog: dict[str, Any]) -> None:
    """标注只写到 meta_root（Fly 上仅小 JSON）。"""
    path = meta_root() / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_result_status(value: Any) -> str:
    v = (str(value or "")).strip().lower()
    if v in RESULT_STATUSES:
        return v
    return RESULT_UNKNOWN


def enrich_record(r: dict[str, Any]) -> dict[str, Any]:
    row = dict(r)
    row["result_status"] = normalize_result_status(row.get("result_status"))
    cats = row.get("categories")
    if not isinstance(cats, list) or not cats:
        primary = (row.get("category") or "").strip()
        cats = [primary] if primary else []
    cats = [str(c).strip() for c in cats if str(c).strip()]
    row["categories"] = cats
    if cats and not row.get("category"):
        row["category"] = cats[0]
    row["category_label"] = "、".join(category_label(c) for c in cats) if cats else "未分类"
    return row


def list_records(
    *,
    person: str = "self",
    purpose: str = "",
    category: str = "",
    categories: list[str] | None = None,
    q: str = "",
    include_empty_purpose: bool = True,
) -> list[dict[str, Any]]:
    rows = load_catalog().get("records") or []
    needle = (q or "").strip().lower()
    wanted: set[str] = set()
    if categories:
        wanted = {c.strip() for c in categories if c and str(c).strip()}
    elif category:
        wanted = {category.strip()}
    out = []
    for r in rows:
        if person and r.get("person") != person:
            continue
        enriched = enrich_record(r)
        if wanted:
            rec_cats = set(enriched.get("categories") or [])
            if not (wanted & rec_cats):
                continue
        p = (enriched.get("purpose") or "").strip()
        if purpose:
            if purpose.lower() not in p.lower():
                continue
        elif not include_empty_purpose and not p:
            continue
        if needle:
            blob = " ".join(
                [
                    str(enriched.get("exam_name") or ""),
                    str(enriched.get("purpose") or ""),
                    str(enriched.get("purpose_note") or ""),
                    str(enriched.get("notes") or ""),
                    str(enriched.get("hospital") or ""),
                    str(enriched.get("category_label") or ""),
                    str(enriched.get("file_name") or ""),
                ]
            ).lower()
            if needle not in blob:
                continue
        out.append(enriched)
    out.sort(key=lambda x: (x.get("exam_date") or "", x.get("exam_name") or ""), reverse=True)
    return out


def get_record(record_id: str) -> Optional[dict[str, Any]]:
    for r in load_catalog().get("records") or []:
        if r.get("id") == record_id:
            return enrich_record(r)
    return None


def group_events(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for r in records:
        eid = r.get("event_id") or f"loose-{r.get('id')}"
        if eid not in buckets:
            buckets[eid] = {
                "event_id": eid,
                "exam_date": r.get("exam_date") or "",
                "purpose": r.get("purpose") or "",
                "purpose_note": r.get("purpose_note") or "",
                "records": [],
            }
        buckets[eid]["records"].append(r)
        # 事件目的：取第一条非空
        if not buckets[eid]["purpose"] and r.get("purpose"):
            buckets[eid]["purpose"] = r.get("purpose") or ""
            buckets[eid]["purpose_note"] = r.get("purpose_note") or ""
    events = list(buckets.values())
    for ev in events:
        names = []
        for rec in ev["records"]:
            n = rec.get("exam_name") or ""
            if n and n not in names:
                names.append(n)
        ev["exam_names"] = names
        ev["record_count"] = len(ev["records"])
        statuses = [normalize_result_status(x.get("result_status")) for x in ev["records"]]
        if RESULT_ABNORMAL in statuses:
            ev["day_status"] = RESULT_ABNORMAL
        elif statuses and all(s == RESULT_NORMAL for s in statuses):
            ev["day_status"] = RESULT_NORMAL
        else:
            ev["day_status"] = RESULT_UNKNOWN
    events.sort(key=lambda e: e.get("exam_date") or "", reverse=True)
    return events


def purpose_stats(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: OrderedDict[str, int] = OrderedDict()
    for r in records:
        p = (r.get("purpose") or "").strip() or "未标注"
        counts[p] = counts.get(p, 0) + 1
    return [{"purpose": k, "count": v} for k, v in counts.items()]


def available_years(records: list[dict[str, Any]] | None = None) -> list[int]:
    rows = records if records is not None else list_records(person="self")
    years: set[int] = set()
    for r in rows:
        d = (r.get("exam_date") or "")[:4]
        if d.isdigit():
            years.add(int(d))
    if not years:
        years.add(date.today().year)
    return sorted(years, reverse=True)


def year_choices(records: list[dict[str, Any]] | None = None) -> list[int]:
    """下拉可选年份：有数据的年份 ± 扩展到近年。"""
    data_years = available_years(records)
    today_y = date.today().year
    lo = min(min(data_years), today_y - 8)
    hi = max(max(data_years), today_y)
    return list(range(hi, lo - 1, -1))


def _day_status(recs: list[dict[str, Any]]) -> str:
    if not recs:
        return ""
    statuses = [normalize_result_status(r.get("result_status")) for r in recs]
    if RESULT_ABNORMAL in statuses:
        return RESULT_ABNORMAL
    if all(s == RESULT_NORMAL for s in statuses):
        return RESULT_NORMAL
    return RESULT_UNKNOWN


def build_year_calendar(year: int, records: list[dict[str, Any]]) -> dict[str, Any]:
    """按年生成 12 个月日历格子 + 按日材料列表。"""
    by_date: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        d = (r.get("exam_date") or "").strip()
        if len(d) < 10 or not d.startswith(f"{year}-"):
            continue
        by_date.setdefault(d, []).append(r)

    month_summaries = []
    months_out = []
    for month in range(1, 13):
        weeks = cal_mod.Calendar(firstweekday=0).monthdayscalendar(year, month)
        weeks_out = []
        month_count = 0
        month_abn = 0
        for week in weeks:
            days_out = []
            for day in week:
                if day == 0:
                    days_out.append({"empty": True})
                    continue
                key = f"{year:04d}-{month:02d}-{day:02d}"
                day_recs = by_date.get(key) or []
                status = _day_status(day_recs)
                if day_recs:
                    month_count += len(day_recs)
                    if status == RESULT_ABNORMAL:
                        month_abn += 1
                days_out.append(
                    {
                        "empty": False,
                        "day": day,
                        "date": key,
                        "count": len(day_recs),
                        "status": status,
                        "records": [
                            {
                                "id": x.get("id"),
                                "exam_name": x.get("exam_name") or "",
                                "purpose": x.get("purpose") or "",
                                "purpose_note": x.get("purpose_note") or "",
                                "notes": x.get("notes") or "",
                                "hospital": x.get("hospital") or "",
                                "category": x.get("category") or "",
                                "categories": x.get("categories")
                                or ([x.get("category")] if x.get("category") else []),
                                "category_label": category_label(str(x.get("category") or ""))
                                if not x.get("categories")
                                else "、".join(
                                    category_label(str(c))
                                    for c in (x.get("categories") or [])
                                ),
                                "result_status": normalize_result_status(x.get("result_status")),
                                "file_relpath": x.get("file_relpath") or "",
                                "file_name": x.get("file_name") or "",
                            }
                            for x in day_recs
                        ],
                    }
                )
            weeks_out.append(days_out)
        month_summaries.append(
            {
                "month": month,
                "count": month_count,
                "abnormal_days": month_abn,
                "has_records": month_count > 0,
            }
        )
        months_out.append(
            {
                "month": month,
                "label": f"{month}月",
                "weeks": weeks_out,
                "count": month_count,
                "abnormal_days": month_abn,
            }
        )

    return {
        "year": year,
        "months": months_out,
        "month_summaries": month_summaries,
        "days_with_records": sum(1 for v in by_date.values() if v),
        "record_count": sum(len(v) for v in by_date.values()),
        "abnormal_days": sum(
            1 for v in by_date.values() if _day_status(v) == RESULT_ABNORMAL
        ),
    }


def resolve_asset(relpath: str) -> Optional[Path]:
    """先查可写目录（新上传），再查镜像/仓库原件。"""
    rel = (relpath or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    for root in (data_write_root().resolve(), bundled_health_root().resolve()):
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.is_file():
            return path
    return None


def load_watchlist() -> dict[str, Any]:
    for path in (meta_root() / "watchlist.json", _bundled_meta_file("watchlist.json")):
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return {"items": []}


def load_purpose_tags() -> list[dict[str, str]]:
    for path in (meta_root() / "purposes.json", _bundled_meta_file("purposes.json")):
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("tags") or []
    return load_catalog().get("purpose_tags") or []


_SAFE_NAME = re.compile(r"^[\w\u4e00-\u9fff\-_\.\+\(\)（）]+$", re.UNICODE)
_SAFE_FILE_STEM = re.compile(r"[^\w\u4e00-\u9fff\-]+", re.UNICODE)

ALLOWED_UPLOAD_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"})
MAX_UPLOAD_BYTES = 12 * 1024 * 1024


def _safe_stem(text: str, fallback: str = "材料") -> str:
    s = _SAFE_FILE_STEM.sub("_", (text or "").strip()).strip("._")
    return (s or fallback)[:40]


def _make_record_id(category: str, exam_date: str, exam_name: str) -> str:
    base = f"{category}-{exam_date.replace('-', '')}-{_safe_stem(exam_name)}"
    catalog = load_catalog()
    existing = {r.get("id") for r in (catalog.get("records") or [])}
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def add_uploaded_record(
    *,
    file_storage,
    exam_date: str,
    categories: list[str] | None = None,
    category: str = "",
    exam_name: str = "",
    notes: str = "",
    purpose: str = "",
    purpose_note: str = "",
    hospital: str = "",
) -> tuple[Optional[dict[str, Any]], str]:
    """
    保存上传文件并写入 catalog。
    命名：YYYY-MM-DD_名称_医院.ext（与档案整理规则一致）。
    """
    exam_date = (exam_date or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", exam_date):
        return None, "请填写正确日期（YYYY-MM-DD）"

    valid_ids = {c["id"] for c in load_doc_categories()}
    cats = [c.strip() for c in (categories or []) if c and str(c).strip()]
    if not cats and (category or "").strip():
        cats = [category.strip()]
    cats = [c for c in cats if c in valid_ids]
    if not cats:
        return None, "请至少选择一个类别"
    primary = cats[0]

    if file_storage is None or not getattr(file_storage, "filename", None):
        return None, "请选择要上传的文件"

    original = Path(file_storage.filename).name
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXT:
        return None, "仅支持图片或 PDF（jpg/png/webp/gif/pdf）"

    raw = file_storage.read()
    if not raw:
        return None, "文件为空"
    if len(raw) > MAX_UPLOAD_BYTES:
        return None, "文件过大（上限 12MB）"

    name = (exam_name or "").strip() or Path(original).stem
    hospital_s = (hospital or "").strip() or "未注医院"
    folder = category_folder(primary)
    # 统一命名：YYYY-MM-DD_检查名_医院.ext
    file_name = f"{exam_date}_{_safe_stem(name)}_{_safe_stem(hospital_s)}{ext}"

    rel = f"{folder}/{file_name}".replace("\\", "/")
    dest_dir = data_write_root() / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file_name
    if dest.exists():
        stem = f"{exam_date}_{_safe_stem(name)}_{_safe_stem(hospital_s)}"
        n = 2
        while dest.exists():
            dest = dest_dir / f"{stem}_{n}{ext}"
            n += 1
        file_name = dest.name
        rel = f"{folder}/{file_name}".replace("\\", "/")

    dest.write_bytes(raw)

    record_id = _make_record_id(primary, exam_date, name)
    event_id = f"evt-self-{exam_date}"
    github_path = f"医疗/数据/{rel}"
    rec = {
        "id": record_id,
        "person": "self",
        "category": primary,
        "categories": cats,
        "exam_date": exam_date,
        "exam_name": name,
        "hospital": (hospital or "").strip(),
        "specimen": "",
        "file_name": file_name,
        "file_relpath": rel,
        "source_original": original,
        "notes": (notes or "").strip(),
        "purpose": (purpose or "").strip(),
        "purpose_note": (purpose_note or "").strip(),
        "event_id": event_id,
        "indicators_status": "pending" if "lab" in cats else "n/a",
        "indicators_file": None,
        "result_status": RESULT_UNKNOWN,
        "github_path": github_path,
    }

    catalog = load_catalog()
    records = list(catalog.get("records") or [])
    records.append(rec)
    catalog["records"] = records
    stats = dict(catalog.get("stats") or {})
    for cid in cats:
        stats[cid] = int(stats.get(cid) or 0) + 1
    stats["total"] = len(records)
    catalog["stats"] = stats
    catalog["version"] = max(int(catalog.get("version") or 2), 2)
    save_catalog(catalog)

    bundled_cat = _bundled_meta_file("catalog.json")
    writable_cat = meta_root() / "catalog.json"
    if writable_cat.resolve() != bundled_cat.resolve() and not (os.environ.get("BILL_DATA_DIR") or "").strip():
        bundled_cat.parent.mkdir(parents=True, exist_ok=True)
        bundled_cat.write_text(writable_cat.read_text(encoding="utf-8"), encoding="utf-8")

    # 正式站：额外 commit 进私密 GitHub（Volume 仅作立刻预览缓存）
    from .github_sync import github_sync_enabled, sync_upload_to_github

    if github_sync_enabled():
        ok, detail = sync_upload_to_github(
            github_path=github_path,
            file_bytes=raw,
            catalog=catalog,
            exam_name=name,
        )
        enriched = enrich_record(rec)
        enriched["github_synced"] = ok
        enriched["github_sync_detail"] = detail
        if not ok:
            return enriched, f"已暂存到服务器，但写入 GitHub 失败：{detail}"
        return enriched, ""

    return enrich_record(rec), ""


def update_record_meta(
    record_id: str,
    *,
    purpose: str | None = None,
    purpose_note: str | None = None,
    result_status: str | None = None,
    category: str | None = None,
    categories: list[str] | None = None,
    notes: str | None = None,
    exam_name: str | None = None,
) -> bool:
    catalog = load_catalog()
    found = False
    valid_ids = {c["id"] for c in load_doc_categories()}
    for r in catalog.get("records") or []:
        if r.get("id") == record_id:
            if purpose is not None:
                r["purpose"] = (purpose or "").strip()
            if purpose_note is not None:
                r["purpose_note"] = (purpose_note or "").strip()
            if result_status is not None:
                r["result_status"] = normalize_result_status(result_status)
            if categories is not None:
                cats = [c for c in categories if c in valid_ids]
                if cats:
                    r["categories"] = cats
                    r["category"] = cats[0]
            elif category is not None:
                cid = (category or "").strip()
                if cid in valid_ids:
                    r["category"] = cid
                    r["categories"] = [cid]
            if notes is not None:
                r["notes"] = (notes or "").strip()
            if exam_name is not None:
                r["exam_name"] = (exam_name or "").strip()
            found = True
            break
    if found:
        save_catalog(catalog)
        from .github_sync import github_sync_enabled, sync_catalog_to_github

        if github_sync_enabled():
            sync_catalog_to_github(catalog, reason=f"annotate {record_id}")
    return found


def update_record_purpose(record_id: str, purpose: str, purpose_note: str = "") -> bool:
    return update_record_meta(record_id, purpose=purpose, purpose_note=purpose_note)
