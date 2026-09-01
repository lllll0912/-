"""收藏 Blueprint（仅所有者）。"""

from __future__ import annotations

import mimetypes

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from auth import can_write, has_module_access

from .store import (
    backfill_catalog_dates,
    build_collection_timeline,
    collection_years,
    delete_image,
    delete_movie,
    delete_person,
    format_stars,
    get_movie,
    get_person,
    images_payload,
    list_images,
    list_movies,
    list_people,
    list_person_names,
    movie_stats,
    normalize_score,
    resolve_image,
    save_catalog,
    save_image_bytes,
    save_artwork_files,
    save_uploads,
    build_pics_context,
    today_str,
    upsert_movie,
    upsert_person,
    load_catalog,
)
from .metadata import backfill_missing_metadata, fetch_movie_artwork, lookup_movie_metadata

collection_bp = Blueprint(
    "collection",
    __name__,
    url_prefix="/collection",
    template_folder="templates",
    static_folder="static",
    static_url_path="/collection-static",
)


@collection_bp.before_request
def _guard():
    if request.endpoint and request.endpoint.endswith(".static"):
        return None
    if not has_module_access("collection"):
        abort(403)
    if request.method not in ("GET", "HEAD") and not can_write():
        abort(403)


@collection_bp.route("/")
def collection_home():
    try:
        return _render_collection_home()
    except Exception:
        from flask import current_app

        current_app.logger.exception("collection_home failed")
        raise


def _render_collection_home():
    backfill_catalog_dates()
    # 人物 Tab 已下线，统一走作品
    tab = "movies"
    q = (request.args.get("q") or "").strip()
    person = (request.args.get("person") or "").strip()
    filter_mode = (request.args.get("filter") or "all").strip()
    sort = (request.args.get("sort") or "added_desc").strip()
    view = (request.args.get("view") or "grid").strip()
    if filter_mode not in ("all", "incomplete", "scored", "unscored"):
        filter_mode = "all"
    if sort not in ("added_desc", "added_asc", "score_desc", "id_asc", "name_asc"):
        sort = "added_desc"
    if view not in ("grid", "calendar"):
        view = "grid"
    pics_ctx = build_pics_context()
    movies = list_movies(
        q, filter_mode=filter_mode, sort=sort, person=person, pics_ctx=pics_ctx
    )
    person_names = list_person_names()
    stats = movie_stats(pics_ctx=pics_ctx)
    years = collection_years(list_movies("", pics_ctx=pics_ctx))
    year_raw = request.args.get("year")
    try:
        year = int(year_raw) if year_raw else years[0]
    except (TypeError, ValueError):
        year = years[0]
    if year not in years:
        years = sorted(set(years) | {year}, reverse=True)
    show_calendar = view == "calendar"
    calendar_movies = (
        list_movies("", filter_mode=filter_mode, sort=sort, person=person, pics_ctx=pics_ctx)
        if show_calendar
        else movies
    )
    timeline = build_collection_timeline(year, calendar_movies) if show_calendar else None
    return render_template(
        "home.html",
        tab=tab,
        view=view,
        q=q,
        person=person,
        filter_mode=filter_mode,
        sort=sort,
        movies=movies if not show_calendar else calendar_movies,
        people=[],
        person_names=person_names,
        timeline=timeline,
        recommends=[],
        years=years,
        year=year,
        movie_count=stats["total"],
        people_count=0,
        today=today_str(),
        can_edit=can_write(),
    )


@collection_bp.route("/movies", methods=["POST"])
def movie_save():
    old_id = (request.form.get("old_id") or "").strip()
    next_filter = (request.form.get("next_filter") or "all").strip()
    next_sort = (request.form.get("next_sort") or "added_desc").strip()
    next_year = (request.form.get("next_year") or "").strip()
    next_view = (request.form.get("next_view") or "grid").strip()
    data = {
        "id": (request.form.get("id") or "").strip(),
        "title": (request.form.get("title") or "").strip(),
        "description": (request.form.get("description") or "").strip(),
        "person": (request.form.get("person") or "").strip(),
        "score": (request.form.get("score") or "").strip(),
        "tags": (request.form.get("tags") or "").strip(),
        "added_date": (request.form.get("added_date") or "").strip(),
    }
    rec, err = upsert_movie(data, old_id=old_id)
    if err:
        flash(err, "error")
    else:
        files = request.files.getlist("files")
        if files and any(getattr(f, "filename", None) for f in files):
            n, uerr = save_uploads(rec["id"], files)
            if uerr and n == 0:
                flash(f"已保存条目，上传失败：{uerr}", "error")
            elif n:
                flash(f"已保存，并上传 {n} 张图", "success")
            else:
                flash("已保存", "success")
        elif not list_images(rec["id"]):
            art = fetch_movie_artwork(rec["id"], max_images=10)
            files_bytes = art.get("files") or []
            if files_bytes:
                n, uerr = save_artwork_files(rec["id"], files_bytes, merge=False)
                if uerr and n == 0:
                    flash(f"已保存条目，自动抓图失败：{uerr}", "error")
                elif n:
                    flash(f"已保存，并自动抓取 {n} 张封面/剧照", "success")
                else:
                    flash("已保存", "success")
            else:
                hint = art.get("error") or "未找到封面"
                flash(f"已保存（未能自动抓图：{hint}）", "success")
        else:
            flash("已保存", "success")
    return redirect(
        url_for(
            "collection.collection_home",
            tab="movies",
            filter=next_filter,
            sort=next_sort,
            view=next_view if next_view in ("grid", "calendar") else "grid",
            **({"year": next_year} if next_year else {}),
        )
    )


@collection_bp.route("/movies/<path:mov_id>/delete", methods=["POST"])
def movie_delete(mov_id: str):
    remove_pics = (request.form.get("remove_pics") or "") == "1"
    if delete_movie(mov_id, remove_pics=remove_pics):
        flash("已删除作品", "success")
    else:
        flash("未找到该作品", "error")
    return redirect(url_for("collection.collection_home", tab="movies"))


@collection_bp.route("/people", methods=["POST"])
def person_save():
    old_name = (request.form.get("old_name") or "").strip()
    next_filter = (request.form.get("next_filter") or "all").strip()
    next_sort = (request.form.get("next_sort") or "added_desc").strip()
    next_year = (request.form.get("next_year") or "").strip()
    next_view = (request.form.get("next_view") or "grid").strip()
    data = {
        "name": (request.form.get("name") or "").strip(),
        "description": (request.form.get("description") or "").strip(),
        "classic": (request.form.get("classic") or "").strip(),
        "kind": (request.form.get("kind") or "").strip(),
        "score": (request.form.get("score") or "").strip(),
        "tags": (request.form.get("tags") or "").strip(),
        "added_date": (request.form.get("added_date") or "").strip(),
    }
    rec, err = upsert_person(data, old_name=old_name)
    if err:
        flash(err, "error")
    else:
        files = request.files.getlist("files")
        if files and any(getattr(f, "filename", None) for f in files):
            n, uerr = save_uploads(rec["name"], files)
            if uerr and n == 0:
                flash(f"已保存条目，上传失败：{uerr}", "error")
            elif n:
                flash(f"已保存，并上传 {n} 张图", "success")
            else:
                flash("已保存", "success")
        else:
            flash("已保存", "success")
    return redirect(
        url_for(
            "collection.collection_home",
            tab="people",
            filter=next_filter,
            sort=next_sort,
        )
    )


@collection_bp.route("/people/<path:name>/delete", methods=["POST"])
def person_delete(name: str):
    remove_pics = (request.form.get("remove_pics") or "") == "1"
    if delete_person(name, remove_pics=remove_pics):
        flash("已删除人物", "success")
    else:
        flash("未找到该人物", "error")
    return redirect(url_for("collection.collection_home"))


@collection_bp.route("/api/backfill-metadata", methods=["POST"])
def api_backfill_metadata():
    """后台批量补全女优名（不阻塞页面）。"""
    result = backfill_missing_metadata(max_fetch=20)
    return jsonify({"ok": True, **result})


@collection_bp.route("/api/movies/lookup")
def api_movie_lookup():
    code = (request.args.get("code") or request.args.get("id") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "missing_code"}), 400
    payload = lookup_movie_metadata(code)
    status = 200 if payload.get("ok") else 404
    return jsonify(payload), status


@collection_bp.route("/api/movies/<path:mov_id>/score", methods=["POST", "PATCH"])
def api_movie_score(mov_id: str):
    """图库内快速点星评分。"""
    movie = get_movie(mov_id)
    if not movie:
        abort(404)
    body = request.get_json(silent=True) or {}
    raw = body.get("score")
    if raw is None:
        raw = request.form.get("score") or ""
    score, score_err = normalize_score(str(raw))
    if score_err:
        return jsonify({"ok": False, "error": score_err}), 400

    catalog = load_catalog()
    updated = None
    for i, m in enumerate(catalog.get("movies") or []):
        if (m.get("id") or "").strip() == mov_id:
            catalog["movies"][i] = {**m, "score": score}
            updated = catalog["movies"][i]
            break
    if updated is None:
        abort(404)
    save_catalog(catalog)
    return jsonify(
        {
            "ok": True,
            "id": mov_id,
            "score": score,
            "stars": format_stars(score),
        }
    )


@collection_bp.route("/api/movies/<path:mov_id>/fetch-artwork", methods=["POST"])
def api_movie_fetch_artwork(mov_id: str):
    """补抓封面/剧照；已有图时默认合并（刷新封面 + 追加 sample）。"""
    if not get_movie(mov_id):
        abort(404)
    merge = (request.args.get("merge") or request.form.get("merge") or "1").strip() not in ("0", "false", "no")
    had = bool(list_images(mov_id))
    art = fetch_movie_artwork(mov_id, max_images=10)
    files_bytes = art.get("files") or []
    if not files_bytes:
        payload = images_payload(mov_id)
        payload.update({"ok": False, "saved": 0, "error": art.get("error") or "no_images"})
        return jsonify(payload), 404
    n, err = save_artwork_files(mov_id, files_bytes, merge=merge or had)
    payload = images_payload(mov_id)
    payload.update({"ok": n > 0 or (had and not err), "saved": n, "error": err})
    return jsonify(payload), (200 if (n or not err) else 400)


@collection_bp.route("/api/movies/<path:mov_id>/images")
def api_movie_images(mov_id: str):
    if not get_movie(mov_id):
        abort(404)
    return jsonify(images_payload(mov_id))


@collection_bp.route("/api/people/<path:name>/images")
def api_person_images(name: str):
    if not get_person(name):
        abort(404)
    return jsonify(images_payload(name))


@collection_bp.route("/api/movies/<path:mov_id>/images", methods=["POST"])
def api_movie_upload(mov_id: str):
    if not get_movie(mov_id):
        abort(404)
    files = request.files.getlist("files")
    n, err = save_uploads(mov_id, files)
    payload = images_payload(mov_id)
    payload.update({"ok": n > 0, "saved": n, "error": err})
    return jsonify(payload), (200 if n else 400)


@collection_bp.route("/api/people/<path:name>/images", methods=["POST"])
def api_person_upload(name: str):
    if not get_person(name):
        abort(404)
    files = request.files.getlist("files")
    n, err = save_uploads(name, files)
    payload = images_payload(name)
    payload.update({"ok": n > 0, "saved": n, "error": err})
    return jsonify(payload), (200 if n else 400)


@collection_bp.route("/api/movies/<path:mov_id>/images/<path:filename>", methods=["DELETE"])
def api_movie_delete_image(mov_id: str, filename: str):
    if not get_movie(mov_id):
        abort(404)
    ok = delete_image(mov_id, filename)
    payload = images_payload(mov_id)
    payload["ok"] = ok
    return jsonify(payload), (200 if ok else 404)


@collection_bp.route("/api/people/<path:name>/images/<path:filename>", methods=["DELETE"])
def api_person_delete_image(name: str, filename: str):
    if not get_person(name):
        abort(404)
    ok = delete_image(name, filename)
    payload = images_payload(name)
    payload["ok"] = ok
    return jsonify(payload), (200 if ok else 404)


@collection_bp.route("/pic/<path:folder_id>/<path:filename>")
def serve_pic(folder_id: str, filename: str):
    path = resolve_image(folder_id, filename)
    if not path:
        abort(404)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return send_file(path, mimetype=mime)
