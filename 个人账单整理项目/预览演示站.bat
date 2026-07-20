@echo off
chcp 65001 >nul
cd /d "%~dp0site"
echo 演示站预览 http://127.0.0.1:8502
python -m http.server 8502
