import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

from db.connector import get_cursor


app = Flask(__name__, static_folder="public", static_url_path="")
CORS(app)


def select_daily_poem(today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """选择某一天的推荐诗句，并在数据库中做标记。

    逻辑：
    1. 如果该日已经有 done=1 且 done_date=当日 的记录，则直接返回；
    2. 否则在 done=0 中按 id 升序选一条，更新为今日已推送；
    3. 如果所有都已推送过，则按 done_date DESC, id DESC 取最近的一条作为 fallback。
    """
    today = today or date.today()

    with get_cursor() as cur:
        # 已经为今天选过
        cur.execute(
            """
            SELECT * FROM poems
            WHERE done = 1 AND done_date = %s
            ORDER BY id
            LIMIT 1
            """,
            (today,),
        )
        row = cur.fetchone()
        if row:
            return row

        # 从未推送的里选一条
        cur.execute(
            """
            SELECT * FROM poems
            WHERE done = 0
            ORDER BY id
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row:
            poem_id = row["id"]
            cur.execute(
                "UPDATE poems SET done = 1, done_date = %s WHERE id = %s",
                (today, poem_id),
            )
            row["done"] = 1
            row["done_date"] = today
            return row

        # 全部推送完了，退化为取最新一条
        cur.execute(
            """
            SELECT * FROM poems
            WHERE done_date IS NOT NULL
            ORDER BY done_date DESC, id DESC
            LIMIT 1
            """
        )
        return cur.fetchone()


def schedule_daily_job() -> None:
    """使用 APScheduler 配置每天 22:00 自动选诗。"""
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        func=lambda: select_daily_poem(),
        trigger="cron",
        hour=22,
        minute=0,
        id="select_daily_poem_22",
        replace_existing=True,
    )
    scheduler.start()


@app.route("/")
def index_page():
    """Web UI 首页，返回每日诗句小程序风格页面。"""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/today", methods=["GET"])
def api_today():
    """获取“今日推荐”。

    如果今天还没有记录，则会即时选择一条并写入数据库。
    """
    poem = select_daily_poem()
    if not poem:
        return jsonify({"message": "暂无诗句数据"}), 404

    # 将 date / datetime 转成字符串，方便前端使用
    for key in ("poem_date", "done_date", "created_at"):
        v = poem.get(key)
        if isinstance(v, (date, datetime)):
            poem[key] = v.isoformat()
    return jsonify(poem)


@app.route("/api/history", methods=["GET"])
def api_history():
    """获取历史推送记录（所有用户共用的一条时间线）。"""
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("pageSize", 20))
    offset = (page - 1) * page_size

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT * FROM poems
            WHERE done = 1
            ORDER BY done_date DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (page_size, offset),
        )
        rows: List[Dict[str, Any]] = cur.fetchall()

    for row in rows:
        for key in ("poem_date", "done_date", "created_at"):
            v = row.get(key)
            if isinstance(v, (date, datetime)):
                row[key] = v.isoformat()

    return jsonify(rows)


@app.route("/api/favorites", methods=["POST"])
def api_add_favorite():
    """收藏某条诗句。"""
    data = request.get_json(force=True) or {}
    user_id = data.get("userId")
    poem_id = data.get("poemId")
    if not user_id or not poem_id:
        return jsonify({"message": "userId 和 poemId 必填"}), 400

    with get_cursor() as cur:
        cur.execute(
            """
            INSERT IGNORE INTO poem_favorites (user_id, poem_id)
            VALUES (%s, %s)
            """,
            (user_id, poem_id),
        )

    return jsonify({"success": True})


@app.route("/api/favorites", methods=["DELETE"])
def api_remove_favorite():
    """取消收藏某条诗句。"""
    data = request.get_json(force=True) or {}
    user_id = data.get("userId")
    poem_id = data.get("poemId")
    if not user_id or not poem_id:
        return jsonify({"message": "userId 和 poemId 必填"}), 400

    with get_cursor() as cur:
        cur.execute(
            """
            DELETE FROM poem_favorites
            WHERE user_id = %s AND poem_id = %s
            """,
            (user_id, poem_id),
        )

    return jsonify({"success": True})


@app.route("/api/favorites", methods=["GET"])
def api_list_favorites():
    """获取某个用户收藏的诗句列表。"""
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"message": "userId 必填"}), 400

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT p.*
            FROM poem_favorites f
            JOIN poems p ON f.poem_id = p.id
            WHERE f.user_id = %s
            ORDER BY f.created_at DESC
            """,
            (user_id,),
        )
        rows: List[Dict[str, Any]] = cur.fetchall()

    for row in rows:
        for key in ("poem_date", "done_date", "created_at"):
            v = row.get(key)
            if isinstance(v, (date, datetime)):
                row[key] = v.isoformat()

    return jsonify(rows)


def create_app() -> Flask:
    """方便以后在 WSGI / ASGI 中复用。"""
    schedule_daily_job()
    return app


if __name__ == "__main__":
    # 直接运行: python app.py
    schedule_daily_job()
    port = int(os.environ.get("PORT", "8765"))
    app.run(host="0.0.0.0", port=port, debug=False)

