import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional, Dict, List, Any

from rule_manager import infer_category, is_known_category, is_known_l1, l2_to_l1

@dataclass
class ParseOptions:
    year: int = 2025


@dataclass
class ImportOptions:
    year: int = 2025
    travel_tag: str = ""
    travel_keywords: str = ""
    mark_all_travel: bool = False


def _to_float(raw: str) -> Optional[float]:
    clean = raw.strip().replace(",", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", clean):
        return float(clean)
    return None


def _normalize_date(date_token: str, year: int) -> Optional[str]:
    text = date_token.strip().replace(".", "-").replace("/", "-")
    match = re.fullmatch(r"(\d{1,2})-(\d{1,2})", text)
    if not match:
        return None
    month = int(match.group(1))
    day = int(match.group(2))
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _iter_blocks(raw_text: str) -> Iterable[List[str]]:
    for block in re.split(r"\n\s*\n", raw_text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if lines:
            yield lines


def _extract_header_date_and_note(header_line: str, year: int) -> Dict[str, Any]:
    if "；" not in header_line:
        return {"date": None, "note": header_line.strip()}
    date_part, note = header_line.split("；", 1)
    return {"date": _normalize_date(date_part, year), "note": note.strip()}


def _extract_inline_travel_tag(note: str) -> str:
    m = re.search(r"旅游标签[-：:]*[\(（](.+?)[\)）]", note)
    return m.group(1).strip() if m else ""


def _is_travel_record(detail: str, note: str, opts: ImportOptions, inline_tag: str) -> bool:
    if opts.mark_all_travel:
        return True
    if inline_tag:
        return True

    keyword_text = "{} {}".format(detail, note).lower()
    for kw in [k.strip().lower() for k in opts.travel_keywords.split(",") if k.strip()]:
        if kw in keyword_text:
            return True
    return False


def parse_for_staging(raw_text: str, options: Optional[ImportOptions] = None) -> List[Dict[str, Any]]:
    opts = options or ImportOptions()
    staged: List[Dict[str, Any]] = []
    row_index = 0

    for lines in _iter_blocks(raw_text):
        header = _extract_header_date_and_note(lines[0], opts.year)
        note = str(header.get("note", ""))
        bill_date = header.get("date")
        inline_tag = _extract_inline_travel_tag(note)

        if len(lines) == 1:
            row_index += 1
            staged.append(
                {
                    "row_index": row_index,
                    "bill_date": bill_date,
                    "amount": 0.0,
                    "detail": "",
                    "note": note,
                    "direction": "支出",
                    "category_l1": "其他消费",
                    "category": "其他消费",
                    "explicit_category_raw": "",
                    "category_unknown": False,
                    "is_travel": _is_travel_record("", note, opts, inline_tag),
                    "travel_tag": inline_tag or opts.travel_tag,
                    "is_valid": bill_date is not None,
                    "error_msg": "" if bill_date is not None else "日期解析失败",
                }
            )
            continue

        for raw_line in lines[1:]:
            row_index += 1
            parts = [p.strip() for p in raw_line.split("；")]
            detail = parts[0] if parts else ""
            amount = _to_float(parts[1]) if len(parts) >= 2 else None
            is_income = any(p == "收入" for p in parts[2:]) if len(parts) > 2 else False
            direction = "收入" if is_income else "支出"

            explicit_category = ""
            if len(parts) >= 3 and parts[2] and parts[2] != "收入":
                explicit_category = parts[2]
            elif len(parts) >= 4 and parts[2] == "收入":
                explicit_category = parts[3]

            explicit_raw = (explicit_category or "").strip()
            category_unknown = False
            cat_l1 = ""
            cat_l2 = ""
            if explicit_raw:
                mapped = l2_to_l1(explicit_raw, is_income)
                if mapped and (is_known_category(mapped, is_income) or is_known_l1(mapped, is_income)):
                    cat_l2 = mapped
                    cat_l1 = mapped
                elif is_known_category(explicit_raw, is_income) or is_known_l1(explicit_raw, is_income):
                    cat_l2 = explicit_raw
                    cat_l1 = explicit_raw
                else:
                    cat_l2 = explicit_raw
                    cat_l1 = ""
                    category_unknown = True
            else:
                cat_l1, cat_l2 = infer_category(detail, is_income)

            valid = bill_date is not None and amount is not None
            err = ""
            if bill_date is None:
                err = "日期解析失败"
            elif amount is None:
                err = "金额解析失败"

            is_travel = _is_travel_record(detail, note, opts, inline_tag)
            tag = inline_tag or opts.travel_tag

            staged.append(
                {
                    "row_index": row_index,
                    "bill_date": bill_date,
                    "amount": 0.0 if amount is None else amount,
                    "detail": detail,
                    "note": note,
                    "direction": direction,
                    "category_l1": cat_l1,
                    "category": cat_l2,
                    "explicit_category_raw": explicit_raw if category_unknown else "",
                    "category_unknown": category_unknown,
                    "is_travel": is_travel,
                    "travel_tag": tag,
                    "is_valid": valid,
                    "error_msg": err,
                }
            )

    return staged


def parse_bill_text(raw_text: str, options: Optional[ParseOptions] = None) -> List[Dict[str, Any]]:
    opts = options or ParseOptions()
    rows: List[Dict[str, object]] = []

    for lines in _iter_blocks(raw_text):
        if "；" not in lines[0]:
            continue

        header = lines[0]
        date_part, note = header.split("；", 1)
        normalized_date = _normalize_date(date_part, opts.year)
        if not normalized_date:
            continue

        if len(lines) == 1:
            rows.append(
                {
                    "日期": normalized_date,
                    "金额": 0.0,
                    "类型明细": "",
                    "日记": note.strip(),
                    "交易方向": "支出",
                    "一级类型": "其他消费",
                    "类型": "其他消费",
                }
            )
            continue

        for record_line in lines[1:]:
            parts = [p.strip() for p in record_line.split("；")]
            if len(parts) < 2:
                continue

            detail = parts[0]
            amount = _to_float(parts[1])
            if amount is None:
                continue

            is_income = any(p == "收入" for p in parts[2:])
            direction = "收入" if is_income else "支出"

            explicit_category = ""
            if len(parts) >= 3 and parts[2] and parts[2] != "收入":
                explicit_category = parts[2]
            elif len(parts) >= 4 and parts[2] == "收入" and parts[3]:
                explicit_category = parts[3]

            if explicit_category:
                mapped = l2_to_l1(explicit_category, is_income) or explicit_category
                cat_l2 = mapped
                cat_l1 = mapped
            else:
                cat_l1, cat_l2 = infer_category(detail, is_income)

            rows.append(
                {
                    "日期": normalized_date,
                    "金额": amount,
                    "类型明细": detail,
                    "日记": note.strip(),
                    "交易方向": direction,
                    "一级类型": cat_l1,
                    "类型": cat_l2,
                }
            )

    valid_rows: List[Dict[str, Any]] = []
    for row in rows:
        day = row.get("日期", "")
        if isinstance(day, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            row["年月"] = day[:7]
            valid_rows.append(row)
    return valid_rows


def summarize(records: List[Dict[str, Any]]) -> Dict[str, float]:
    if not records:
        return {"total_income": 0.0, "total_expense": 0.0, "net": 0.0}

    income = sum(float(r.get("金额", 0.0)) for r in records if r.get("交易方向") == "收入")
    expense = sum(float(r.get("金额", 0.0)) for r in records if r.get("交易方向") == "支出")
    return {"total_income": income, "total_expense": expense, "net": income - expense}


def filter_records(
    records: List[Dict[str, Any]],
    start_date: str = "",
    end_date: str = "",
    directions: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    keyword: str = "",
) -> List[Dict[str, Any]]:
    directions = directions or []
    categories = categories or []
    key = keyword.strip().lower()

    result: List[Dict[str, Any]] = []
    for r in records:
        day = str(r.get("日期", ""))
        direction = str(r.get("交易方向", ""))
        category = str(r.get("类型", ""))
        detail = str(r.get("类型明细", ""))
        note = str(r.get("日记", ""))

        if start_date and day < start_date:
            continue
        if end_date and day > end_date:
            continue
        if directions and direction not in directions:
            continue
        if categories and category not in categories:
            continue
        if key and key not in detail.lower() and key not in note.lower():
            continue
        result.append(r)
    return result


def monthly_summary(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bucket: Dict[str, Dict[str, float]] = {}
    for r in records:
        month = str(r.get("年月", ""))
        direction = str(r.get("交易方向", ""))
        amount = float(r.get("金额", 0.0))
        bucket.setdefault(month, {"收入": 0.0, "支出": 0.0})
        if direction in ("收入", "支出"):
            bucket[month][direction] += amount

    output: List[Dict[str, Any]] = []
    for month in sorted(bucket.keys()):
        output.append({"年月": month, "收入": round(bucket[month]["收入"], 2), "支出": round(bucket[month]["支出"], 2)})
    return output


def category_summary(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bucket: Dict[str, float] = {}
    for r in records:
        key = "{}|{}".format(r.get("交易方向", ""), r.get("类型", ""))
        bucket[key] = bucket.get(key, 0.0) + float(r.get("金额", 0.0))

    rows: List[Dict[str, Any]] = []
    for key, amount in bucket.items():
        direction, category = key.split("|", 1)
        rows.append({"交易方向": direction, "类型": category, "金额": round(amount, 2)})
    rows.sort(key=lambda x: (x["交易方向"], -x["金额"]))
    return rows
