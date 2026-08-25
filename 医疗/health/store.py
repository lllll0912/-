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


def meta_root() -> Path:
    """
    可写元数据（catalog / 目的标注）。
    - 本机：直接写 医疗/数据/_meta
    - Fly：只写 Volume 上很小的 JSON（/data/health/_meta），不存照片
    """
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / "health" / "_meta"
    return bundled_health_root() / "_meta"


def health_root() -> Path:
    """原件根目录：始终用镜像/仓库里的数据，避免照片占云盘。"""
    return bundled_health_root()


def _bundled_meta_file(name: str) -> Path:
    return bundled_health_root() / "_meta" / name


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
    return row


def list_records(
    *,
    person: str = "self",
    purpose: str = "",
    category: str = "",
    include_empty_purpose: bool = True,
) -> list[dict[str, Any]]:
    rows = load_catalog().get("records") or []
    out = []
    for r in rows:
        if person and r.get("person") != person:
            continue
        if category and r.get("category") != category:
            continue
        p = (r.get("purpose") or "").strip()
        if purpose:
            if p != purpose:
                continue
        elif not include_empty_purpose and not p:
            continue
        out.append(enrich_record(r))
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
                                "hospital": x.get("hospital") or "",
                                "category": x.get("category") or "",
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
    """原件只从镜像/仓库 医疗/数据 读取（不占 Fly 云盘）。"""
    rel = (relpath or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    root = bundled_health_root().resolve()
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path


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


def update_record_meta(
    record_id: str,
    *,
    purpose: str | None = None,
    purpose_note: str | None = None,
    result_status: str | None = None,
) -> bool:
    catalog = load_catalog()
    found = False
    for r in catalog.get("records") or []:
        if r.get("id") == record_id:
            if purpose is not None:
                r["purpose"] = (purpose or "").strip()
            if purpose_note is not None:
                r["purpose_note"] = (purpose_note or "").strip()
            if result_status is not None:
                r["result_status"] = normalize_result_status(result_status)
            found = True
            break
    if found:
        save_catalog(catalog)
    return found


def update_record_purpose(record_id: str, purpose: str, purpose_note: str = "") -> bool:
    return update_record_meta(record_id, purpose=purpose, purpose_note=purpose_note)
