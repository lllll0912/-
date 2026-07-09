#!/usr/bin/env bash
# 一键启动：自动创建虚拟环境、安装依赖、启动 Flask（在项目根目录执行即可）
set -e
cd "$(dirname "$0")"

VENV_DIR="${BILL_VENV:-.venv}"
PYTHON="${PYTHON:-python3}"

if [[ ! -d "$VENV_DIR" ]]; then
  echo ">>> 创建虚拟环境: $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

echo ">>> 安装/检查依赖 (requirements.txt)"
pip install -q -r requirements.txt

echo ">>> 启动服务 http://127.0.0.1:8501 （Ctrl+C 停止）"
exec python app.py
