"""飞猪 FlyAI CLI 的 Python 封装。底层通过 flyai-cli 调用飞猪 MCP 服务。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


class FlyAIError(RuntimeError):
    pass


def _resolve_flyai_cmd() -> list[str]:
    """按优先级查找 flyai 可执行文件。"""
    local_bin = ROOT / "node_modules" / ".bin" / "flyai"
    if local_bin.with_suffix(".cmd").exists():
        return [str(local_bin.with_suffix(".cmd"))]
    if local_bin.exists():
        return [str(local_bin)]

    global_bin = shutil.which("flyai")
    if global_bin:
        return [global_bin]

    npx = shutil.which("npx")
    if npx:
        return [npx, "flyai"]

    raise FlyAIError(
        "未找到 flyai 命令。请先安装 Node.js，然后在「飞猪MCP」目录运行：\n"
        "  npm install\n"
        "或全局安装：npm i -g @fly-ai/flyai-cli"
    )


def run_flyai(args: list[str], timeout: int = 120) -> dict[str, Any]:
    """执行 flyai 子命令，返回解析后的 JSON。"""
    cmd = _resolve_flyai_cmd() + args
    env = os.environ.copy()
    # 让本地 node_modules/.bin 优先
    local_bin = ROOT / "node_modules" / ".bin"
    if local_bin.exists():
        env["PATH"] = str(local_bin) + os.pathsep + env.get("PATH", "")

    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise FlyAIError(f"请求超时（{timeout}s）：{' '.join(args)}") from exc
    except FileNotFoundError as exc:
        raise FlyAIError("无法启动 flyai，请确认已安装 Node.js 并执行 npm install") from exc

    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)

    stdout = proc.stdout.strip()
    if not stdout:
        raise FlyAIError(
            f"flyai 无输出（exit={proc.returncode}）：{' '.join(args)}\n"
            f"{proc.stderr.strip()}"
        )

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise FlyAIError(f"无法解析 JSON 输出：{stdout[:500]}") from exc

    # Windows 上 flyai-cli 偶发在输出 JSON 后异常退出，但数据仍可用
    if data.get("status", 0) == 0:
        return data

    if proc.returncode != 0:
        raise FlyAIError(data.get("message") or f"flyai 失败（exit={proc.returncode}）")

    return data


def ai_search(query: str) -> dict[str, Any]:
    return run_flyai(["ai-search", "--query", query])


def keyword_search(query: str) -> dict[str, Any]:
    return run_flyai(["keyword-search", "--query", query])


def search_hotel(
    dest_name: str,
    *,
    poi_name: str | None = None,
    check_in: str | None = None,
    check_out: str | None = None,
    max_price: int | None = None,
    sort: str | None = None,
) -> dict[str, Any]:
    args = ["search-hotel", "--dest-name", dest_name]
    if poi_name:
        args += ["--poi-name", poi_name]
    if check_in:
        args += ["--check-in-date", check_in]
    if check_out:
        args += ["--check-out-date", check_out]
    if max_price is not None:
        args += ["--max-price", str(max_price)]
    if sort:
        args += ["--sort", sort]
    return run_flyai(args)


def search_flight(
    origin: str,
    destination: str | None = None,
    *,
    dep_date: str | None = None,
    back_date: str | None = None,
    sort_type: int | None = None,
) -> dict[str, Any]:
    args = ["search-flight", "--origin", origin]
    if destination:
        args += ["--destination", destination]
    if dep_date:
        args += ["--dep-date", dep_date]
    if back_date:
        args += ["--back-date", back_date]
    if sort_type is not None:
        args += ["--sort-type", str(sort_type)]
    return run_flyai(args)


def search_train(
    origin: str,
    destination: str | None = None,
    *,
    dep_date: str | None = None,
    sort_type: int | None = None,
) -> dict[str, Any]:
    args = ["search-train", "--origin", origin]
    if destination:
        args += ["--destination", destination]
    if dep_date:
        args += ["--dep-date", dep_date]
    if sort_type is not None:
        args += ["--sort-type", str(sort_type)]
    return run_flyai(args)


def search_poi(
    city_name: str,
    *,
    keyword: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    args = ["search-poi", "--city-name", city_name]
    if keyword:
        args += ["--keyword", keyword]
    if category:
        args += ["--category", category]
    return run_flyai(args)
