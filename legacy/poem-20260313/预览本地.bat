@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 正在从 poem.txt 生成 poems.json ...
python scripts\build_poems_json.py
if errorlevel 1 (
  echo 构建失败，请确认已安装 Python。
  pause
  exit /b 1
)

echo.
echo 本地预览：浏览器打开 http://127.0.0.1:8765
echo 按 Ctrl+C 可停止。
echo.
cd site
python -m http.server 8765
