"""飞猪MCP 命令行入口：探索 FlyAI 接口并生成旅行攻略。"""

from __future__ import annotations

import argparse
import json
import sys

from flyai_client import (
    FlyAIError,
    ai_search,
    keyword_search,
    run_flyai,
    search_flight,
    search_hotel,
    search_poi,
    search_train,
)
from guide_builder import build_trip_guide


def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_probe(_: argparse.Namespace) -> int:
    """快速探测 CLI 是否可用。"""
    try:
        data = keyword_search("杭州三日游")
        print("[OK] FlyAI 连接正常")
        _print_json(data)
        return 0
    except FlyAIError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1


def cmd_ai(args: argparse.Namespace) -> int:
    try:
        _print_json(ai_search(args.query))
        return 0
    except FlyAIError as exc:
        print(exc, file=sys.stderr)
        return 1


def cmd_keyword(args: argparse.Namespace) -> int:
    try:
        _print_json(keyword_search(args.query))
        return 0
    except FlyAIError as exc:
        print(exc, file=sys.stderr)
        return 1


def cmd_hotel(args: argparse.Namespace) -> int:
    try:
        _print_json(
            search_hotel(
                args.dest,
                poi_name=args.poi,
                check_in=args.check_in,
                check_out=args.check_out,
                max_price=args.max_price,
                sort=args.sort,
            )
        )
        return 0
    except FlyAIError as exc:
        print(exc, file=sys.stderr)
        return 1


def cmd_flight(args: argparse.Namespace) -> int:
    try:
        _print_json(
            search_flight(
                args.origin,
                args.destination,
                dep_date=args.dep_date,
                back_date=args.back_date,
                sort_type=args.sort,
            )
        )
        return 0
    except FlyAIError as exc:
        print(exc, file=sys.stderr)
        return 1


def cmd_train(args: argparse.Namespace) -> int:
    try:
        _print_json(
            search_train(
                args.origin,
                args.destination,
                dep_date=args.dep_date,
                sort_type=args.sort,
            )
        )
        return 0
    except FlyAIError as exc:
        print(exc, file=sys.stderr)
        return 1


def cmd_poi(args: argparse.Namespace) -> int:
    try:
        _print_json(
            search_poi(args.city, keyword=args.keyword, category=args.category)
        )
        return 0
    except FlyAIError as exc:
        print(exc, file=sys.stderr)
        return 1


def cmd_guide(args: argparse.Namespace) -> int:
    try:
        markdown, path = build_trip_guide(
            args.destination,
            args.days,
            origin=args.origin,
            budget=args.budget,
            check_in=args.check_in,
            check_out=args.check_out,
            dep_date=args.dep_date,
            companions=args.companions,
        )
        print(f"攻略已保存：{path}")
        if args.print:
            print("\n" + markdown)
        return 0
    except FlyAIError as exc:
        print(exc, file=sys.stderr)
        return 1


def cmd_help(_: argparse.Namespace) -> int:
    try:
        data = run_flyai(["--help"])
        _print_json(data)
    except FlyAIError:
        print("请在本目录执行 npm install 后重试：flyai --help")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="飞猪MCP — 探索 FlyAI Agent 接口，查询旅行信息并生成攻略"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_probe = sub.add_parser("probe", help="探测 FlyAI 是否可用")
    p_probe.set_defaults(func=cmd_probe)

    p_ai = sub.add_parser("ai", help="AI 语义搜索（行程规划推荐）")
    p_ai.add_argument("query", help="自然语言查询")
    p_ai.set_defaults(func=cmd_ai)

    p_kw = sub.add_parser("keyword", help="关键词搜索（综合推荐）")
    p_kw.add_argument("query", help="搜索关键词")
    p_kw.set_defaults(func=cmd_keyword)

    p_hotel = sub.add_parser("hotel", help="酒店搜索")
    p_hotel.add_argument("dest", help="目的地城市")
    p_hotel.add_argument("--poi", help="附近景点")
    p_hotel.add_argument("--check-in", help="入住日期 YYYY-MM-DD")
    p_hotel.add_argument("--check-out", help="离店日期 YYYY-MM-DD")
    p_hotel.add_argument("--max-price", type=int, help="每晚最高价格")
    p_hotel.add_argument("--sort", default="rate_desc", help="排序方式")
    p_hotel.set_defaults(func=cmd_hotel)

    p_flight = sub.add_parser("flight", help="航班搜索")
    p_flight.add_argument("origin", help="出发城市")
    p_flight.add_argument("destination", nargs="?", help="目的地城市")
    p_flight.add_argument("--dep-date", help="出发日期")
    p_flight.add_argument("--back-date", help="返程日期")
    p_flight.add_argument("--sort", type=int, default=3, help="排序：3=低价优先")
    p_flight.set_defaults(func=cmd_flight)

    p_train = sub.add_parser("train", help="火车搜索")
    p_train.add_argument("origin", help="出发城市")
    p_train.add_argument("destination", nargs="?", help="目的地城市")
    p_train.add_argument("--dep-date", help="出发日期")
    p_train.add_argument("--sort", type=int, default=3)
    p_train.set_defaults(func=cmd_train)

    p_poi = sub.add_parser("poi", help="景点搜索")
    p_poi.add_argument("city", help="城市名")
    p_poi.add_argument("--keyword", help="景点关键词")
    p_poi.add_argument("--category", help="景点类别")
    p_poi.set_defaults(func=cmd_poi)

    p_guide = sub.add_parser("guide", help="生成综合旅行攻略（Markdown）")
    p_guide.add_argument("destination", help="目的地，如：杭州")
    p_guide.add_argument("days", type=int, help="游玩天数")
    p_guide.add_argument("--origin", help="出发城市（可选，用于查交通）")
    p_guide.add_argument("--budget", type=int, help="人均预算（元）")
    p_guide.add_argument("--check-in", help="入住日期")
    p_guide.add_argument("--check-out", help="离店日期")
    p_guide.add_argument("--dep-date", help="出发日期")
    p_guide.add_argument("--companions", default="自由行", help="出行类型")
    p_guide.add_argument("--print", action="store_true", help="同时打印攻略内容")
    p_guide.set_defaults(func=cmd_guide)

    p_help = sub.add_parser("flyai-help", help="查看 flyai CLI 帮助")
    p_help.set_defaults(func=cmd_help)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
