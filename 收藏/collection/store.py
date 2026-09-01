"""收藏：作品 / 人物目录（JSON + 本地图片，无 MySQL）。"""

from __future__ import annotations

import calendar as cal_mod
import json
import os
import re
import shutil
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_UPLOAD_FILES = 40
_SAFE_FOLDER = re.compile(r"[/\\]+|\.\.")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def bundled_root() -> Path:
    return Path(__file__).resolve().parents[1] / "数据"


def data_write_root() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / "collection"
    return bundled_root()


def pics_root() -> Path:
    return data_write_root() / "pics"


def meta_root() -> Path:
    return data_write_root() / "_meta"


def catalog_path() -> Path:
    return meta_root() / "catalog.json"


def _bundled_catalog() -> Path:
    return bundled_root() / "_meta" / "catalog.json"


def today_str() -> str:
    return date.today().isoformat()


def normalize_date(value: str, *, default: str = "") -> str:
    s = (value or "").strip()
    if _DATE_RE.fullmatch(s):
        return s
    return default or today_str()


def folder_name(record_id: str) -> str:
    s = (record_id or "").strip()
    s = _SAFE_FOLDER.sub("_", s)
    return s[:80] or "untitled"


def normalize_movie_id(code: str) -> str:
    """番号规范化，如 vdd131 → VDD-131。"""
    s = (code or "").strip().upper()
    if not s:
        return ""
    s = re.sub(r"\s+", "", s)
    m = re.match(r"^([A-Z]{2,10})-?(\d{2,5})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return s


def empty_catalog() -> dict[str, Any]:
    return {"version": 2, "movies": [], "people": []}


def load_catalog() -> dict[str, Any]:
    for path in (catalog_path(), _bundled_catalog()):
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data.setdefault("movies", [])
                data.setdefault("people", [])
                return data
            except (json.JSONDecodeError, OSError):
                continue
    return empty_catalog()


def save_catalog(catalog: dict[str, Any], *, sync_github: bool = True) -> None:
    path = catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    catalog["version"] = max(int(catalog.get("version") or 2), 2)
    path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # 本机：写 bundled 目录供本地开发（已在 .gitignore，勿 push 运行态）
    bundled = _bundled_catalog()
    if path.resolve() != bundled.resolve() and not (os.environ.get("BILL_DATA_DIR") or "").strip():
        bundled.parent.mkdir(parents=True, exist_ok=True)
        bundled.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    if sync_github:
        try:
            from .github_sync import github_sync_enabled, sync_catalog_to_github

            if github_sync_enabled():
                sync_catalog_to_github(catalog, reason="update catalog")
        except Exception:
            pass


def _folder_mtime_date(folder_id: str) -> str:
    folder = pics_root() / folder_name(folder_id)
    if not folder.is_dir():
        return today_str()
    try:
        ts = folder.stat().st_mtime
        return datetime.fromtimestamp(ts).date().isoformat()
    except OSError:
        return today_str()


def ensure_meta_defaults(row: dict[str, Any], *, kind: str) -> dict[str, Any]:
    r = dict(row)
    key = (r.get("id") if kind == "movie" else r.get("name")) or ""
    if not (r.get("added_date") or "").strip():
        r["added_date"] = _folder_mtime_date(str(key)) if key else today_str()
    else:
        r["added_date"] = normalize_date(str(r.get("added_date") or ""), default=today_str())
    r["score"] = str(r.get("score") or "").strip()
    r["description"] = str(r.get("description") or "").strip()
    r["tags"] = str(r.get("tags") or "").strip()
    return r


def is_incomplete_movie(row: dict[str, Any]) -> bool:
    return not str(row.get("score") or "").strip() or not str(row.get("description") or "").strip()


def is_incomplete_person(row: dict[str, Any]) -> bool:
    return not str(row.get("score") or "").strip() or not str(row.get("description") or "").strip()


def backfill_catalog_dates() -> int:
    catalog = load_catalog()
    changed = 0
    movies = []
    for m in catalog.get("movies") or []:
        before = (m.get("added_date") or "").strip()
        nm = ensure_meta_defaults(m, kind="movie")
        if (nm.get("added_date") or "") != before:
            changed += 1
        movies.append(nm)
    people = []
    for p in catalog.get("people") or []:
        before = (p.get("added_date") or "").strip()
        np = ensure_meta_defaults(p, kind="person")
        if (np.get("added_date") or "") != before:
            changed += 1
        people.append(np)
    if changed:
        catalog["movies"] = movies
        catalog["people"] = people
        save_catalog(catalog, sync_github=False)
    return changed


def list_images(folder_id: str, *, pics_ctx: Optional[dict[str, list[dict[str, Any]]]] = None) -> list[dict[str, Any]]:
    """合并本机/Volume 与 GitHub 索引，避免缓存里只有封面时丢掉其余图。"""
    fid = folder_name(folder_id)
    if pics_ctx is not None:
        return _sort_images(list(pics_ctx.get(fid) or []), fid)

    by_name: dict[str, dict[str, Any]] = {}

    def _add_from_dir(folder: Path) -> None:
        if not folder.is_dir():
            return
        for p in folder.iterdir():
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                by_name[p.name] = {"name": p.name, "size": p.stat().st_size}

    _add_from_dir(pics_root() / fid)
    bundled = bundled_root() / "pics" / fid
    if bundled.resolve() != (pics_root() / fid).resolve():
        _add_from_dir(bundled)

    try:
        from .github_sync import list_github_pics

        for item in list_github_pics(fid):
            name = item.get("name") or ""
            if name and name not in by_name:
                by_name[name] = {"name": name, "size": int(item.get("size") or 0)}
    except Exception:
        pass

    return _sort_images(list(by_name.values()), fid)


def _cover_sort_key(name: str) -> tuple[int, str]:
    low = (name or "").lower()
    if low.startswith("cover"):
        return (0, low)
    if low.startswith("000_cover") or low == "cover.jpg" or low == "cover.webp":
        return (0, low)
    return (1, low)


def _sort_images(items: list[dict[str, Any]], folder_id: str = "") -> list[dict[str, Any]]:
    """封面类文件名始终排在最前，便于列表与图库默认展示。"""
    if not items:
        return []
    return sorted(items, key=lambda x: (_cover_sort_key(str(x.get("name") or ""))))


def build_pics_context() -> dict[str, list[dict[str, Any]]]:
    """一次扫描本地 pics + GitHub 索引，供批量 enrich 复用。"""
    ctx: dict[str, dict[str, dict[str, Any]]] = {}

    def _add(folder: Path) -> None:
        if not folder.is_dir():
            return
        for sub in folder.iterdir():
            if not sub.is_dir():
                continue
            fid = sub.name
            bucket = ctx.setdefault(fid, {})
            for p in sub.iterdir():
                if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                    bucket[p.name] = {"name": p.name, "size": p.stat().st_size}

    _add(pics_root())
    bundled_pics = bundled_root() / "pics"
    if bundled_pics.resolve() != pics_root().resolve():
        _add(bundled_pics)

    try:
        from .github_sync import load_all_github_pics

        for fid, items in load_all_github_pics().items():
            bucket = ctx.setdefault(fid, {})
            for item in items:
                name = item.get("name") or ""
                if name and name not in bucket:
                    bucket[name] = {"name": name, "size": int(item.get("size") or 0)}
    except Exception:
        pass

    return {fid: _sort_images(list(items.values()), fid) for fid, items in ctx.items()}


def images_payload(folder_id: str) -> dict[str, Any]:
    items = list_images(folder_id)
    return {
        "folder": folder_name(folder_id),
        "count": len(items),
        "total_bytes": sum(i["size"] for i in items),
        "images": items,
    }


def enrich_movie(row: dict[str, Any], *, pics_ctx: Optional[dict[str, list[dict[str, Any]]]] = None) -> dict[str, Any]:
    r = ensure_meta_defaults(row, kind="movie")
    fid = r.get("pic_folder") or r.get("id") or ""
    imgs = list_images(str(fid), pics_ctx=pics_ctx)
    r["image_count"] = len(imgs)
    r["cover"] = imgs[0]["name"] if imgs else ""
    r["pic_folder"] = folder_name(str(fid)) if fid else ""
    r["incomplete"] = is_incomplete_movie(r)
    r["stars"] = format_stars(r.get("score"))
    r["stars_n"] = stars_count(r.get("score"))
    return r


def enrich_person(row: dict[str, Any], *, pics_ctx: Optional[dict[str, list[dict[str, Any]]]] = None) -> dict[str, Any]:
    r = ensure_meta_defaults(row, kind="person")
    fid = r.get("pic_folder") or r.get("name") or ""
    imgs = list_images(str(fid), pics_ctx=pics_ctx)
    r["image_count"] = len(imgs)
    r["cover"] = imgs[0]["name"] if imgs else ""
    r["pic_folder"] = folder_name(str(fid)) if fid else ""
    r["incomplete"] = is_incomplete_person(r)
    r["stars"] = format_stars(r.get("score"))
    r["stars_n"] = stars_count(r.get("score"))
    return r


def list_movies(
    q: str = "",
    *,
    filter_mode: str = "all",
    sort: str = "added_desc",
    pics_ctx: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> list[dict[str, Any]]:
    qn = (q or "").strip().lower()
    ctx = pics_ctx if pics_ctx is not None else build_pics_context()
    rows = [enrich_movie(m, pics_ctx=ctx) for m in load_catalog().get("movies") or []]
    if qn:
        rows = [
            m
            for m in rows
            if qn
            in " ".join(
                [
                    str(m.get("id") or ""),
                    str(m.get("title") or ""),
                    str(m.get("description") or ""),
                    str(m.get("person") or ""),
                    str(m.get("tags") or ""),
                ]
            ).lower()
        ]
    mode = (filter_mode or "all").strip()
    if mode == "incomplete":
        rows = [m for m in rows if m.get("incomplete")]
    elif mode == "scored":
        rows = [m for m in rows if str(m.get("score") or "").strip()]
    elif mode == "unscored":
        rows = [m for m in rows if not str(m.get("score") or "").strip()]

    sk = (sort or "added_desc").strip()
    if sk == "score_desc":
        rows.sort(key=lambda m: (-_score(m.get("score")), str(m.get("id") or "")))
    elif sk == "id_asc":
        rows.sort(key=lambda m: str(m.get("id") or "").lower())
    elif sk == "added_asc":
        rows.sort(key=lambda m: (str(m.get("added_date") or ""), str(m.get("id") or "")))
    else:
        rows.sort(key=lambda m: (str(m.get("added_date") or ""), str(m.get("id") or "")), reverse=True)
    return rows


def list_people(
    q: str = "",
    *,
    filter_mode: str = "all",
    sort: str = "added_desc",
    pics_ctx: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> list[dict[str, Any]]:
    qn = (q or "").strip().lower()
    ctx = pics_ctx if pics_ctx is not None else build_pics_context()
    rows = [enrich_person(p, pics_ctx=ctx) for p in load_catalog().get("people") or []]
    if qn:
        rows = [
            p
            for p in rows
            if qn
            in " ".join(
                [
                    str(p.get("name") or ""),
                    str(p.get("description") or ""),
                    str(p.get("classic") or ""),
                    str(p.get("kind") or ""),
                    str(p.get("tags") or ""),
                ]
            ).lower()
        ]
    mode = (filter_mode or "all").strip()
    if mode == "incomplete":
        rows = [p for p in rows if p.get("incomplete")]
    elif mode == "scored":
        rows = [p for p in rows if str(p.get("score") or "").strip()]

    sk = (sort or "added_desc").strip()
    if sk == "score_desc":
        rows.sort(key=lambda p: (-_score(p.get("score")), str(p.get("name") or "")))
    elif sk == "name_asc":
        rows.sort(key=lambda p: str(p.get("name") or "").lower())
    else:
        rows.sort(key=lambda p: (str(p.get("added_date") or ""), str(p.get("name") or "")), reverse=True)
    return rows


def _score(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def normalize_score(value: str) -> tuple[str, str]:
    """评分改为 1–5 星整数。返回 (规范化分数, 错误信息)。空字符串表示未评分。"""
    s = (value or "").strip()
    if not s:
        return "", ""
    try:
        val = float(s)
    except ValueError:
        return "", "评分须为 1–5 的星级"
    # 兼容旧 0–10：自动折算到 1–5
    if val > 5:
        val = round(val / 2)
    val = int(round(val))
    if val < 1 or val > 5:
        return "", "请选择 1–5 星"
    return str(val), ""


def format_stars(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    s, err = normalize_score(raw)
    if err or not s:
        return ""
    n = int(s)
    return "★" * n + "☆" * (5 - n)


def stars_count(value: Any) -> int:
    s, _ = normalize_score(str(value or "").strip())
    return int(s) if s else 0


def get_movie(mov_id: str) -> Optional[dict[str, Any]]:
    mid = (mov_id or "").strip()
    for m in load_catalog().get("movies") or []:
        if (m.get("id") or "").strip() == mid:
            return enrich_movie(m)
    return None


def get_person(name: str) -> Optional[dict[str, Any]]:
    n = (name or "").strip()
    for p in load_catalog().get("people") or []:
        if (p.get("name") or "").strip() == n:
            return enrich_person(p)
    return None


def movie_stats(*, pics_ctx: Optional[dict[str, list[dict[str, Any]]]] = None) -> dict[str, int]:
    ctx = pics_ctx if pics_ctx is not None else build_pics_context()
    rows = [enrich_movie(m, pics_ctx=ctx) for m in load_catalog().get("movies") or []]
    return {
        "total": len(rows),
        "incomplete": sum(1 for m in rows if m.get("incomplete")),
        "unscored": sum(1 for m in rows if not str(m.get("score") or "").strip()),
    }


def upsert_movie(data: dict[str, Any], *, old_id: str = "") -> tuple[Optional[dict[str, Any]], str]:
    mov_id = normalize_movie_id(data.get("id") or "")
    if not mov_id:
        return None, "番号 / ID 必填"
    score, score_err = normalize_score(str(data.get("score") or ""))
    if score_err:
        return None, score_err

    person = (data.get("person") or "").strip()
    title = (data.get("title") or "").strip()
    if not person or not title:
        try:
            from .metadata import apply_metadata_to_movie, lookup_movie_metadata

            meta = lookup_movie_metadata(mov_id)
            merged = apply_metadata_to_movie({"person": person, "title": title}, meta)
            person = (merged.get("person") or person).strip()
            title = (merged.get("title") or title).strip()
        except Exception:
            pass

    catalog = load_catalog()
    movies = list(catalog.get("movies") or [])
    key = (old_id or mov_id).strip()
    existing_idx = next((i for i, m in enumerate(movies) if (m.get("id") or "") == key), -1)
    if existing_idx < 0 and any((m.get("id") or "") == mov_id for m in movies):
        return None, "该番号已存在"

    prev = movies[existing_idx] if existing_idx >= 0 else {}

    if old_id and old_id != mov_id:
        err = _migrate_folder(old_id, mov_id)
        if err:
            return None, err

    added = normalize_date(
        str(data.get("added_date") or ""),
        default=str(prev.get("added_date") or "") or today_str(),
    )

    row = {
        "id": mov_id,
        "title": title,
        "description": (data.get("description") or "").strip(),
        "person": person,
        "score": score,
        "tags": (data.get("tags") or "").strip(),
        "added_date": added,
        "pic_folder": folder_name(mov_id),
    }
    if existing_idx >= 0:
        movies[existing_idx] = row
    else:
        movies.append(row)
    catalog["movies"] = movies
    save_catalog(catalog)
    return enrich_movie(row), ""


def delete_movie(mov_id: str, *, remove_pics: bool = False) -> bool:
    catalog = load_catalog()
    mid = (mov_id or "").strip()
    before = len(catalog.get("movies") or [])
    catalog["movies"] = [m for m in (catalog.get("movies") or []) if (m.get("id") or "") != mid]
    if len(catalog["movies"]) == before:
        return False
    save_catalog(catalog)
    if remove_pics:
        folder = pics_root() / folder_name(mid)
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
    return True


def upsert_person(data: dict[str, Any], *, old_name: str = "") -> tuple[Optional[dict[str, Any]], str]:
    name = (data.get("name") or "").strip()
    if not name:
        return None, "名称必填"
    score, score_err = normalize_score(str(data.get("score") or ""))
    if score_err:
        return None, score_err

    catalog = load_catalog()
    people = list(catalog.get("people") or [])
    key = (old_name or name).strip()
    existing_idx = next((i for i, p in enumerate(people) if (p.get("name") or "") == key), -1)
    if existing_idx < 0 and any((p.get("name") or "") == name for p in people):
        return None, "该名称已存在"

    prev = people[existing_idx] if existing_idx >= 0 else {}

    if old_name and old_name != name:
        err = _migrate_folder(old_name, name)
        if err:
            return None, err

    added = normalize_date(
        str(data.get("added_date") or ""),
        default=str(prev.get("added_date") or "") or today_str(),
    )

    row = {
        "name": name,
        "description": (data.get("description") or "").strip(),
        "classic": (data.get("classic") or "").strip(),
        "kind": (data.get("kind") or "").strip(),
        "score": score,
        "tags": (data.get("tags") or "").strip(),
        "added_date": added,
        "pic_folder": folder_name(name),
    }
    if existing_idx >= 0:
        people[existing_idx] = row
    else:
        people.append(row)
    catalog["people"] = people
    save_catalog(catalog)
    return enrich_person(row), ""


def delete_person(name: str, *, remove_pics: bool = False) -> bool:
    catalog = load_catalog()
    n = (name or "").strip()
    before = len(catalog.get("people") or [])
    catalog["people"] = [p for p in (catalog.get("people") or []) if (p.get("name") or "") != n]
    if len(catalog["people"]) == before:
        return False
    save_catalog(catalog)
    if remove_pics:
        folder = pics_root() / folder_name(n)
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
    return True


def _migrate_folder(old_id: str, new_id: str) -> str:
    old = pics_root() / folder_name(old_id)
    new = pics_root() / folder_name(new_id)
    if not old.is_dir():
        return ""
    try:
        if new.exists():
            for p in old.iterdir():
                if not p.is_file():
                    continue
                target = new / p.name
                if target.exists():
                    target = new / f"{int(time.time() * 1000)}_{p.name}"
                shutil.move(str(p), str(target))
            try:
                old.rmdir()
            except OSError:
                pass
        else:
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(new))
    except OSError as e:
        return f"图片目录迁移失败：{e}"
    return ""


def resolve_image(folder_id: str, filename: str) -> Optional[Path]:
    name = Path(filename or "").name
    if not name or name != filename or ".." in name:
        return None
    fid = folder_name(folder_id)
    path = (pics_root() / fid / name).resolve()
    root = pics_root().resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if path.is_file():
        return path

    bundled = (bundled_root() / "pics" / fid / name).resolve()
    try:
        bundled.relative_to((bundled_root() / "pics").resolve())
        if bundled.is_file():
            return bundled
    except ValueError:
        pass

    # 正式站缓存未命中：从 GitHub 拉一份落到 Volume 再返回
    try:
        from .github_sync import fetch_github_file, github_sync_enabled, repo_pic_path

        if github_sync_enabled():
            raw = fetch_github_file(repo_pic_path(fid, name))
            if raw:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                return path
    except Exception:
        pass
    return None


def save_artwork_files(folder_id: str, files: list[tuple[str, bytes]], *, merge: bool = False) -> tuple[int, str]:
    """保存抓取到的封面/剧照。merge=True 时覆盖旧 cover* 并追加新 sample。"""
    if not files:
        return 0, "没有图片"
    existing = {img["name"] for img in list_images(folder_id)}
    prepared: list[tuple[str, bytes]] = []
    for fn, raw in files:
        low = (fn or "").lower()
        ext = Path(fn or "img.jpg").suffix.lower() or ".jpg"
        if low.startswith("cover"):
            prepared.append((f"cover{ext}", raw))
            continue
        if merge and fn in existing:
            continue
        prepared.append((fn, raw))
    if merge and not prepared:
        return 0, ""
    return save_image_bytes(folder_id, prepared)


def save_image_bytes(folder_id: str, files: list[tuple[str, bytes]]) -> tuple[int, str]:
    """将已下载的 (filename, bytes) 写入本地/Volume，并在正式站同步 GitHub。"""
    folder = pics_root() / folder_name(folder_id)
    folder.mkdir(parents=True, exist_ok=True)
    if not files:
        return 0, "没有图片"
    saved = 0
    uploaded: dict[str, bytes] = {}
    stamp = int(time.time() * 1000)
    for i, (original, raw) in enumerate(files[:MAX_UPLOAD_FILES]):
        if not raw:
            continue
        if len(raw) > MAX_UPLOAD_BYTES:
            return saved, "单张图片超过 12MB"
        ext = Path(original or "").suffix.lower()
        if ext not in IMAGE_EXTS:
            ext = ".jpg"
        stem = Path(original or "img").stem
        # 抓取封面保留 cover 前缀，便于排序置顶
        if stem.lower().startswith("cover") and re.match(r"^cover(\.[a-z]+)?$", stem, re.I):
            out_name = f"cover{ext}"
        else:
            safe = re.sub(r"[^A-Za-z0-9._\u4e00-\u9fff-]+", "_", stem)[:60] or "img"
            out_name = f"{stamp + i}_{safe}{ext}"
        out = folder / out_name
        out.write_bytes(raw)
        if not (os.environ.get("BILL_DATA_DIR") or "").strip():
            bundled_dir = bundled_root() / "pics" / folder_name(folder_id)
            if bundled_dir.resolve() != folder.resolve():
                bundled_dir.mkdir(parents=True, exist_ok=True)
                (bundled_dir / out_name).write_bytes(raw)
        try:
            from .github_sync import repo_pic_path

            uploaded[repo_pic_path(folder_name(folder_id), out_name)] = raw
        except Exception:
            pass
        saved += 1
    if saved == 0:
        return 0, "没有成功保存的文件"

    try:
        from .github_sync import github_sync_enabled, sync_uploads_to_github

        if github_sync_enabled() and uploaded:
            ok, detail = sync_uploads_to_github(
                uploads=uploaded,
                catalog=load_catalog(),
                label=folder_name(folder_id),
            )
            if not ok:
                return saved, f"已暂存到服务器，但写入 GitHub 失败：{detail}"
    except Exception as e:
        return saved, f"已暂存到服务器，但写入 GitHub 异常：{e}"
    return saved, ""


def save_uploads(folder_id: str, files) -> tuple[int, str]:
    """本机写仓库目录；正式站写 Volume 缓存并 commit 进 GitHub。"""
    if not files:
        return 0, "未选择文件"
    pairs: list[tuple[str, bytes]] = []
    for f in files[:MAX_UPLOAD_FILES]:
        original = getattr(f, "filename", None) or ""
        if not original:
            continue
        ext = Path(original).suffix.lower()
        if ext not in IMAGE_EXTS:
            return 0, f"不支持的格式：{ext or original}"
        raw = f.read()
        if not raw:
            continue
        pairs.append((original, raw))
    return save_image_bytes(folder_id, pairs)


def delete_image(folder_id: str, filename: str) -> bool:
    name = Path(filename or "").name
    if not name or name != filename or ".." in name:
        return False
    fid = folder_name(folder_id)
    deleted_local = False
    for root in (pics_root(), bundled_root() / "pics"):
        path = (root / fid / name).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            continue
        if path.is_file():
            path.unlink(missing_ok=True)
            deleted_local = True

    try:
        from .github_sync import github_sync_enabled, sync_delete_pic_to_github

        if github_sync_enabled():
            ok, _ = sync_delete_pic_to_github(fid, name)
            return deleted_local or ok
    except Exception:
        pass
    return deleted_local


def random_movies(limit: int = 6, movies: Optional[list[dict[str, Any]]] = None) -> list[dict[str, Any]]:
    import random

    rows = movies if movies is not None else list_movies()
    with_pic = [m for m in rows if m.get("image_count")]
    pool = with_pic or rows
    random.shuffle(pool)
    return pool[:limit]


def collection_years(movies: Optional[list[dict[str, Any]]] = None) -> list[int]:
    rows = movies if movies is not None else list_movies()
    years: set[int] = set()
    for m in rows:
        d = (m.get("added_date") or "")[:4]
        if d.isdigit():
            years.add(int(d))
    if not years:
        years.add(date.today().year)
    return sorted(years, reverse=True)


def build_collection_timeline(year: int, movies: list[dict[str, Any]]) -> dict[str, Any]:
    """按 added_date 生成年度收藏时间线（12 个月日历 + 每月作品清单）。"""
    by_date: dict[str, list[dict[str, Any]]] = {}
    for m in movies:
        d = (m.get("added_date") or "").strip()
        if len(d) < 10 or not d.startswith(f"{year}-"):
            continue
        by_date.setdefault(d[:10], []).append(m)

    months_out = []
    month_summaries = []
    for month in range(1, 13):
        weeks = cal_mod.Calendar(firstweekday=0).monthdayscalendar(year, month)
        weeks_out = []
        month_count = 0
        month_items: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for week in weeks:
            days_out = []
            for day in week:
                if day == 0:
                    days_out.append({"empty": True})
                    continue
                key = f"{year:04d}-{month:02d}-{day:02d}"
                day_items = by_date.get(key) or []
                if day_items:
                    month_count += len(day_items)
                    for it in day_items:
                        mid = str(it.get("id") or "")
                        if mid and mid not in seen_ids:
                            seen_ids.add(mid)
                            month_items.append(
                                {
                                    "date": key,
                                    "day": f"{day}日",
                                    "id": mid,
                                    "person": it.get("person") or "",
                                    "title": it.get("title") or "",
                                    "score": it.get("score") or "",
                                    "stars": it.get("stars") or format_stars(it.get("score")),
                                    "cover": it.get("cover") or "",
                                    "pic_folder": it.get("pic_folder") or "",
                                    "image_count": it.get("image_count") or 0,
                                    "description": it.get("description") or "",
                                    "tags": it.get("tags") or "",
                                    "added_date": it.get("added_date") or key,
                                }
                            )
                days_out.append(
                    {
                        "empty": False,
                        "day": day,
                        "date": key,
                        "count": len(day_items),
                        "entries": day_items,
                    }
                )
            weeks_out.append(days_out)
        month_summaries.append(
            {
                "month": month,
                "count": month_count,
                "has_items": month_count > 0,
            }
        )
        months_out.append(
            {
                "month": month,
                "label": f"{month}月",
                "weeks": weeks_out,
                "count": month_count,
                "works": month_items,
            }
        )

    return {
        "year": year,
        "months": months_out,
        "month_summaries": month_summaries,
        "days_with_items": sum(1 for v in by_date.values() if v),
        "item_count": sum(len(v) for v in by_date.values()),
    }
