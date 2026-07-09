@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 静默启动（无黑窗口），供计划任务调用
pythonw -m pip install -r requirements.txt -q >nul 2>&1
start "" pythonw "%~dp0main.py"
