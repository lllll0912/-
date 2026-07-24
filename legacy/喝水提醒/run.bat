@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 正在检查依赖...
python -m pip install -r requirements.txt -q

echo 启动喝水提醒小工具...
python main.py

pause
