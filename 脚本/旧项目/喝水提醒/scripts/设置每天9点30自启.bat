@echo off
chcp 65001 >nul
cd /d "%~dp0"

set TASK_NAME=HydroPulse_WaterReminder
set START_SCRIPT=%~dp0后台启动.bat
set START_TIME=09:30

echo ========================================
echo   喝水提醒 - 安装每天 9:30 自动启动
echo ========================================
echo.

where pythonw >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 pythonw，请先安装 Python。
    pause
    exit /b 1
)

schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    schtasks /Delete /TN "%TASK_NAME%" /F >nul
)

schtasks /Create /TN "%TASK_NAME%" /TR "\"%START_SCRIPT%\"" /SC DAILY /ST %START_TIME% /IT /F

if errorlevel 1 (
    echo [失败] 请右键「以管理员身份运行」本脚本。
    pause
    exit /b 1
)

echo [成功] 已设置每天 %START_TIME% 自动启动。
echo 取消自启请运行：取消每天自启.bat
pause
