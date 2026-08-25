@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ^>^>^> 启动喝水提醒小窗（与网站共用 喝水\数据\water_data.json）
echo.

set "ROOT=%~dp0..\.."
if exist "%ROOT%\.venv\Scripts\python.exe" (
  call "%ROOT%\.venv\Scripts\activate.bat"
)

cd /d "%ROOT%\脚本\旧项目\喝水提醒"
python -m pip install -q -r requirements.txt
python main.py

if errorlevel 1 pause
