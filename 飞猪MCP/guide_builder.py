"""根据 FlyAI 查询结果生成 Markdown 旅行攻略。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from flyai_client import (
    FlyAIError,
    ai_search,
    keyword_search,
    search_flight,
    search_hotel,
    search_poi,
    search_train,
)

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"


def _safe_get_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    inner = data.get("data")
    if isinstance(inner, dict) and "itemList" in inner:
        return inner.get("itemList") or []
    return []


def _format_hotel_items(items: list[dict[str, Any]], limit: int = 5) -> list[str]:
    lines: list[str] = []
    for item in items[:limit]:
        name = item.get("name", "未知酒店")
        price = item.get("price", "")
        score = item.get("score", "")
        score_desc = item.get("scoreDesc", "")
        review = item.get("review", "")
        poi = item.get("interestsPoi", "")
        pic = item.get("mainPic", "")
        url = item.get("detailUrl", "")

        lines.append(f"### {name}")
        if price or score:
            lines.append(f"- 价格：{price}  评分：{score} {score_desc}".strip())
        if poi:
            lines.append(f"- 位置：{poi}")
        if review:
            lines.append(f"- 点评：{review}")
        if pic:
            lines.append(f"![]({pic})")
        if url:
            lines.append(f"[点击预订]({url})")
        lines.append("")
    return lines


def _format_flight_items(items: list[dict[str, Any]], limit: int = 5) -> list[str]:
    lines: list[str] = []
    for item in items[:limit]:
        price = item.get("adultPrice", "")
        url = item.get("jumpUrl", "")
        journeys = item.get("journeys") or []
        lines.append(f"### {price}")
        for journey in journeys:
            for seg in journey.get("segments") or []:
                dep = seg.get("depStationName", "")
                arr = seg.get("arrStationName", "")
                dep_time = seg.get("depDateTime", "")
                arr_time = seg.get("arrDateTime", "")
                flight_no = seg.get("marketingTransportNo", "")
                seat = seg.get("seatClassName", "")
                lines.append(
                    f"- {dep_time} {dep} → {arr_time} {arr}  "
                    f"{flight_no} {seat}  历时 {journey.get('totalDuration', '')}"
                )
        if url:
            lines.append(f"[点击预订]({url})")
        lines.append("")
    return lines


def _format_poi_items(items: list[dict[str, Any]], limit: int = 8) -> list[str]:
    lines: list[str] = []
    for item in items[:limit]:
        name = item.get("name", "未知景点")
        address = item.get("address", "")
        pic = item.get("mainPic", "")
        url = item.get("jumpUrl", "")
        ticket = item.get("ticketInfo") or {}
        ticket_name = ticket.get("ticketName", "")
        ticket_price = ticket.get("price")

        lines.append(f"### {name}")
        if address:
            lines.append(f"- 地址：{address}")
        if ticket_name:
            price_text = f"¥{ticket_price}" if ticket_price else "见详情"
            lines.append(f"- 门票：{ticket_name} {price_text}")
        if pic:
            lines.append(f"![]({pic})")
        if url:
            lines.append(f"[点击预订]({url})")
        lines.append("")
    return lines


def build_trip_guide(
    destination: str,
    days: int,
    *,
    origin: str | None = None,
    budget: int | None = None,
    check_in: str | None = None,
    check_out: str | None = None,
    dep_date: str | None = None,
    companions: str = "自由行",
) -> tuple[str, Path]:
    """综合查询并生成攻略 Markdown，返回内容与保存路径。"""
    budget_part = f"，预算人均{budget}元" if budget else ""
    date_part = ""
    if check_in and check_out:
        date_part = f"，{check_in} 至 {check_out}"
    elif dep_date:
        date_part = f"，出发日期 {dep_date}"

    ai_query = (
        f"{destination}{days}天{companions}攻略"
        f"{date_part}{budget_part}，推荐行程、酒店和必玩景点"
    )

    sections: list[str] = [
        f"# {destination} {days}天旅行攻略",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"> 数据来源：[FlyAI 飞猪开放平台](https://flyai.open.fliggy.com/)",
        "",
        "## 行程概览（AI 语义搜索）",
        "",
    ]

    ai_data = ai_search(ai_query)
    ai_content = ai_data.get("data")
    if isinstance(ai_content, str) and ai_content.strip():
        sections.append(ai_content.strip())
    else:
        sections.append("暂无 AI 行程建议，请查看下方结构化搜索结果。")
    sections.append("")

    hint = ai_data.get("systemMessage")
    if hint:
        sections += ["---", "", str(hint), ""]

    # 关键词补充
    kw_query = f"{destination} {days}日游 攻略"
    kw_data = keyword_search(kw_query)
    kw_items = _safe_get_items(kw_data)
    if kw_items:
        sections += ["## 相关推荐（关键词搜索）", ""]
        for item in kw_items[:6]:
            info = item.get("info") or item
            title = info.get("title", "")
            price = info.get("price", "")
            pic = info.get("picUrl", "")
            url = info.get("jumpUrl", "")
            if title:
                sections.append(f"- **{title}** {price}")
            if pic:
                sections.append(f"![]({pic})")
            if url:
                sections.append(f"[查看详情]({url})")
            sections.append("")

    # 景点
    poi_data = search_poi(destination if len(destination) <= 4 else destination[:2], keyword=destination)
    poi_items = _safe_get_items(poi_data)
    if not poi_items:
        poi_data = search_poi(destination)
        poi_items = _safe_get_items(poi_data)
    if poi_items:
        sections += ["## 热门景点", ""]
        sections += _format_poi_items(poi_items)

    # 酒店
    hotel_kwargs: dict[str, Any] = {}
    if check_in:
        hotel_kwargs["check_in"] = check_in
    if check_out:
        hotel_kwargs["check_out"] = check_out
    if budget:
        hotel_kwargs["max_price"] = budget // max(days, 1)
    hotel_data = search_hotel(destination, sort="rate_desc", **hotel_kwargs)
    hotel_items = _safe_get_items(hotel_data)
    if hotel_items:
        sections += ["## 酒店推荐", ""]
        sections += _format_hotel_items(hotel_items)

    # 交通
    if origin:
        sections += ["## 交通参考", ""]
        if dep_date:
            try:
                flight_data = search_flight(origin, destination, dep_date=dep_date, sort_type=3)
                flight_items = _safe_get_items(flight_data)
                if flight_items:
                    sections += ["### 航班（低价优先）", ""]
                    sections += _format_flight_items(flight_items, limit=3)
            except FlyAIError:
                pass
            try:
                train_data = search_train(origin, destination, dep_date=dep_date, sort_type=3)
                train_items = _safe_get_items(train_data)
                if train_items:
                    sections += ["### 火车（低价优先）", ""]
                    sections += _format_flight_items(train_items, limit=3)
            except FlyAIError:
                pass

    sections += [
        "",
        "---",
        "",
        "*本攻略由飞猪MCP 项目自动生成，价格与库存以飞猪实时页面为准。*",
    ]

    markdown = "\n".join(sections)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in destination)[:20]
    out_path = OUTPUT_DIR / f"攻略_{safe_name}_{days}天_{stamp}.md"
    out_path.write_text(markdown, encoding="utf-8")

    raw_path = OUTPUT_DIR / f"原始数据_{safe_name}_{stamp}.json"
    raw_path.write_text(
        json.dumps(
            {"ai": ai_data, "keyword": kw_data, "poi": poi_data, "hotel": hotel_data},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return markdown, out_path
