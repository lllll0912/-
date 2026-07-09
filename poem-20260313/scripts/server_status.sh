#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_ROOT/scripts/server.pid"
PORT="${PORT:-8765}"

if [ ! -f "$PID_FILE" ]; then
  echo "当前没有记录中的项目服务在运行（未找到 PID 文件）。"
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -z "$PID" ]; then
  echo "PID 文件为空，认为没有服务在运行。"
  exit 0
fi

if ps -p "$PID" >/dev/null 2>&1; then
  echo "服务正在运行：PID=$PID，端口=$PORT"
else
  echo "PID 文件存在但进程不存在，服务实际上已停止。"
fi

