#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_ROOT/scripts/server.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "没有找到 PID 文件，服务大概率已经停止。"
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -z "$PID" ]; then
  echo "PID 文件为空，删除之。"
  rm -f "$PID_FILE"
  exit 0
fi

if ps -p "$PID" >/dev/null 2>&1; then
  echo "正在停止服务 PID=$PID ..."
  kill "$PID" >/dev/null 2>&1 || true
  sleep 1
  if ps -p "$PID" >/dev/null 2>&1; then
    echo "进程仍在，尝试强制结束..."
    kill -9 "$PID" >/dev/null 2>&1 || true
  fi
  echo "服务已停止。"
else
  echo "PID=$PID 的进程不存在，直接清理 PID 文件。"
fi

rm -f "$PID_FILE"

