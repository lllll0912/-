@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo 正在安装 @fly-ai/flyai-cli ...
where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo 未找到 Node.js。请先安装 LTS 版本：https://nodejs.org/
    pause
    exit /b 1
)

call npm install
if errorlevel 1 (
    echo 安装失败，请检查网络或 npm 源。
    pause
    exit /b 1
)

echo.
echo 安装完成。可运行：
echo   npx flyai keyword-search --query "杭州三日游"
echo   python main.py probe
echo.
pause
