@echo off
chcp 65001 >nul
cd /d "%~dp0legacy\喝水提醒"

echo ^>^>^> 启动喝水提醒小窗（与网站共用 data\water_data.json）
echo.

if exist "..\..\.venv\Scripts\python.exe" (
  call "..\..\.venv\Scripts\activate.bat"
)

python -m pip install -q -r requirements.txt
python main.py

if errorlevel 1 pause
