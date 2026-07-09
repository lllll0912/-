@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "VENV_DIR=.venv"
if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo ^>^>^> 创建虚拟环境: %VENV_DIR%
  py -3 -m venv "%VENV_DIR%" 2>nul || python -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"

echo ^>^>^> 安装/检查依赖 (requirements.txt)
pip install -q -r requirements.txt

echo ^>^>^> 启动服务 http://127.0.0.1:8501 （Ctrl+C 停止）
python app.py
