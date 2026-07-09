#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_ROOT/scripts/server.pid"
PORT="${PORT:-8765}"

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" >/dev/null 2>&1; then
    echo "服务已在运行中：PID=$OLD_PID，端口=$PORT"
    exit 0
  fi
fi

cd "$PROJECT_ROOT"
echo "启动 Flask 服务，端口 $PORT ..."
PORT="$PORT" PYTHONPATH="$PROJECT_ROOT" python3 app.py >/dev/null 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
echo "已启动：PID=$NEW_PID，端口=$PORT"

