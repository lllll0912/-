import csv
import json
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple

from db.connector import get_cursor
from rule_manager import get_rules_path, load_rules


BACKUP_PREFIX = "records_backup_"


def get_backup_dir() -> str:
    """本机用项目下 backup/；Fly 用 Volume 上 /data/backup（持久）。"""
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return str(Path(data_dir) / "backup")
    # modules/bills/db → 站点根 /backup
    return str(Path(__file__).resolve().parents[3] / "backup")


BACKUP_DIR = get_backup_dir()  # 兼容旧引用；运行时请用 get_backup_dir()


def _data_root() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir)
    return Path(__file__).resolve().parents[3] / "data"


def _poem_root() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / "poems"
    return Path(__file__).resolve().parents[3] / "poems_data"


def _query_all_records() -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, bill_date, amount, detail, note, direction, category_l1, category,
                   is_travel, travel_tag, travel_companions, source_batch_id, inserted_at, created_at, updated_at
            FROM records
            ORDER BY bill_date DESC, id DESC
            """
        )
        return cur.fetchall()


def _query_travel_profiles() -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(NULLIF(travel_tag,''),'未命名行程') AS travel_tag,
                   GROUP_CONCAT(CASE WHEN travel_companions='' THEN NULL ELSE travel_companions END, '、') AS travel_companions,
                   MIN(bill_date) AS start_date,
                   MAX(bill_date) AS end_date,
                   CAST(julianday(MAX(bill_date)) - julianday(MIN(bill_date)) AS INTEGER) + 1 AS duration_days,
                   COUNT(*) AS record_count,
                   ROUND(SUM(CASE WHEN direction='支出' THEN amount ELSE 0 END), 2) AS expense,
                   ROUND(SUM(CASE WHEN direction='收入' THEN amount ELSE 0 END), 2) AS income
            FROM records
            WHERE is_travel=1
            GROUP BY COALESCE(NULLIF(travel_tag,''),'未命名行程')
            ORDER BY start_date, travel_tag
            """
        )
        return cur.fetchall()


def _safe_read_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = {}
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _export_notes_payload() -> Dict[str, Any]:
    root = _data_root()
    db_path = root / "notes.db"
    notes = []
    if db_path.is_file():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT id, title, content_md, created_at, updated_at FROM notes ORDER BY id"
            )
            notes = [dict(r) for r in cur.fetchall()]
            conn.close()
        except Exception:
            notes = []
    return {"notes": notes, "exported_at": datetime.now().isoformat(timespec="seconds")}


def _export_poems_payload() -> Dict[str, Any]:
    root = _poem_root()
    out: Dict[str, Any] = {"root": str(root)}
    for name in ("poem.txt", "stories.json", "poems.json"):
        path = root / name
        if not path.is_file():
            continue
        if name.endswith(".json"):
            out[name] = _safe_read_json(path, {})
        else:
            try:
                out[name] = path.read_text(encoding="utf-8")
            except Exception:
                out[name] = ""
    return out


def _write_site_extras(base_no_ext: str) -> List[str]:
    """账单以外的站内数据快照（JSON 可读 + 全量 zip）。"""
    written: List[str] = []
    root = _data_root()

    water_path = root / "water_data.json"
    water_out = base_no_ext + "_water.json"
    with open(water_out, "w", encoding="utf-8") as f:
        json.dump(_safe_read_json(water_path, {}), f, ensure_ascii=False, indent=2, default=str)
    written.append(water_out)

    poems_out = base_no_ext + "_poems.json"
    with open(poems_out, "w", encoding="utf-8") as f:
        json.dump(_export_poems_payload(), f, ensure_ascii=False, indent=2, default=str)
    written.append(poems_out)

    notes_out = base_no_ext + "_notes.json"
    with open(notes_out, "w", encoding="utf-8") as f:
        json.dump(_export_notes_payload(), f, ensure_ascii=False, indent=2, default=str)
    written.append(notes_out)

    rules_src = Path(get_rules_path())
    rules_out = base_no_ext + "_category_rules.json"
    if rules_src.is_file():
        shutil.copy2(rules_src, rules_out)
    else:
        with open(rules_out, "w", encoding="utf-8") as f:
            json.dump(load_rules(), f, ensure_ascii=False, indent=2)
    written.append(rules_out)

    hints_src = root / "notes_md_hints.json"
    if hints_src.is_file():
        hints_out = base_no_ext + "_notes_md_hints.json"
        shutil.copy2(hints_src, hints_out)
        written.append(hints_out)

    # 灾难恢复用：数据库与资源目录整包
    ts = Path(base_no_ext).name.replace(BACKUP_PREFIX, "", 1)
    full_zip = str(Path(base_no_ext).parent / "{}{}_fulldata.zip".format(BACKUP_PREFIX, ts))
    with zipfile.ZipFile(full_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "includes": [],
        }

        def add_file(src: Path, arc: str) -> None:
            if src.is_file():
                zf.write(src, arcname=arc)
                manifest["includes"].append(arc)

        add_file(root / "bills.db", "bills.db")
        add_file(root / "bills.db-wal", "bills.db-wal")
        add_file(root / "bills.db-shm", "bills.db-shm")
        add_file(root / "notes.db", "notes.db")
        add_file(root / "notes.db-wal", "notes.db-wal")
        add_file(root / "notes.db-shm", "notes.db-shm")
        add_file(root / "water_data.json", "water_data.json")
        add_file(rules_src, "category_rules.json")
        add_file(hints_src, "notes_md_hints.json")

        poem_root = _poem_root()
        if poem_root.is_dir():
            for p in poem_root.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(poem_root).as_posix()
                    add_file(p, "poems/" + rel)

        assets = root / "notes_assets"
        if assets.is_dir():
            for p in assets.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(assets).as_posix()
                    add_file(p, "notes_assets/" + rel)

        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    written.append(full_zip)

    manifest_out = base_no_ext + "_manifest.json"
    with open(manifest_out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "files": [Path(p).name for p in written],
                "note": "含账单 CSV/类型/旅游，以及喝水、诗词、笔记 JSON；*_fulldata.zip 为可整站恢复的原始数据包。",
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    written.append(manifest_out)
    return written


def write_latest_backup_csv(clear_old: bool = False) -> str:
    """
    按现有命名写入 backup/：
      records_backup_YYYYMMDD_HHMMSS.csv / .txt
      records_backup_..._types/travel/water/poems/notes/...
      records_backup_..._fulldata.zip
    默认保留历史；仅 clear_old=True 时清理旧的 records_backup_*。
    返回主 csv 路径。
    """
    backup_dir = get_backup_dir()
    os.makedirs(backup_dir, exist_ok=True)
    if clear_old:
        for name in os.listdir(backup_dir):
            if name.startswith(BACKUP_PREFIX) and (
                name.endswith(".csv")
                or name.endswith(".txt")
                or name.endswith(".json")
                or name.endswith(".zip")
            ):
                try:
                    os.remove(os.path.join(backup_dir, name))
                except Exception:
                    pass

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, "{}{}.csv".format(BACKUP_PREFIX, ts))
    rows = _query_all_records()
    headers = [
        "id",
        "bill_date",
        "amount",
        "detail",
        "note",
        "direction",
        "category_l1",
        "category",
        "is_travel",
        "travel_tag",
        "travel_companions",
        "source_batch_id",
        "inserted_at",
        "created_at",
        "updated_at",
    ]
    with open(backup_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    txt_file = backup_file[:-4] + ".txt"
    with open(txt_file, "w", encoding="utf-8") as tf:
        for row in rows:
            tf.write(
                "{} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {}\n".format(
                    row.get("bill_date", ""),
                    row.get("detail", ""),
                    row.get("amount", ""),
                    row.get("direction", ""),
                    row.get("category_l1", ""),
                    row.get("category", ""),
                    row.get("is_travel", ""),
                    row.get("travel_tag", ""),
                    row.get("travel_companions", ""),
                    row.get("inserted_at", ""),
                    row.get("id", ""),
                )
            )

    base_no_ext = backup_file[:-4]
    types_file = base_no_ext + "_types.json"
    travel_file = base_no_ext + "_travel.json"
    with open(types_file, "w", encoding="utf-8") as f:
        json.dump(load_rules(), f, ensure_ascii=False, indent=2)
    with open(travel_file, "w", encoding="utf-8") as f:
        json.dump({"travel_profiles": _query_travel_profiles()}, f, ensure_ascii=False, indent=2, default=str)

    types_csv = base_no_ext + "_types.csv"
    with open(types_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["map", "category", "pattern"])
        w.writeheader()
        rules = load_rules()
        for map_name in ("CONSUME_MAP", "INCOME_MAP"):
            flat = rules.get(map_name, {}) or {}
            for name, pattern in flat.items():
                w.writerow(
                    {
                        "map": map_name,
                        "category": name,
                        "pattern": pattern or "",
                    }
                )

    travel_csv = base_no_ext + "_travel.csv"
    with open(travel_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "travel_tag",
                "travel_companions",
                "start_date",
                "end_date",
                "duration_days",
                "record_count",
                "expense",
                "income",
            ],
        )
        w.writeheader()
        for row in _query_travel_profiles():
            w.writerow(row)

    _write_site_extras(base_no_ext)
    return backup_file


def list_backup_bundle_files(main_csv_path: str) -> List[str]:
    """同一时间戳的一套备份文件（含全站数据）。"""
    base = main_csv_path[:-4]
    candidates = [
        main_csv_path,
        base + ".txt",
        base + "_types.json",
        base + "_types.csv",
        base + "_travel.json",
        base + "_travel.csv",
        base + "_water.json",
        base + "_poems.json",
        base + "_notes.json",
        base + "_category_rules.json",
        base + "_notes_md_hints.json",
        base + "_manifest.json",
        base + "_fulldata.zip",
    ]
    return [p for p in candidates if os.path.isfile(p)]


def find_latest_main_csv() -> str:
    """backup/ 中最新的主 csv（排除附属文件）。"""
    import re

    backup_dir = get_backup_dir()
    if not os.path.isdir(backup_dir):
        return ""
    best = ""
    best_mtime = -1.0
    for name in os.listdir(backup_dir):
        if not name.startswith(BACKUP_PREFIX) or not name.endswith(".csv"):
            continue
        rest = name[len(BACKUP_PREFIX) : -4]
        if not re.fullmatch(r"\d{8}_\d{6}", rest):
            continue
        path = os.path.join(backup_dir, name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime >= best_mtime:
            best_mtime = mtime
            best = path
    return best


def create_backup_bundle(clear_old: bool = False) -> Tuple[str, List[str]]:
    main_csv = write_latest_backup_csv(clear_old=clear_old)
    files = list_backup_bundle_files(main_csv)
    return main_csv, files
