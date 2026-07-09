@echo off
chcp 65001 >nul
cd /d "%~dp0"

set TASK_NAME=HydroPulse_WaterReminder
set START_SCRIPT=%~dp0start_silent.bat
set START_TIME=09:30

echo ========================================
echo   喝水提醒 - 安装每日自动启动
echo ========================================
echo.
echo 计划：每天 %START_TIME% 自动启动
echo 脚本：%START_SCRIPT%
echo.

where pythonw >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 pythonw，请先安装 Python 并勾选 Add to PATH。
    pause
    exit /b 1
)

schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo 检测到已有计划任务，正在更新...
    schtasks /Delete /TN "%TASK_NAME%" /F >nul
)

schtasks /Create ^
    /TN "%TASK_NAME%" ^
    /TR "\"%START_SCRIPT%\"" ^
    /SC DAILY ^
    /ST %START_TIME% ^
    /IT ^
    /F

if errorlevel 1 (
    echo.
    echo [失败] 创建计划任务失败。请右键「以管理员身份运行」本脚本后重试。
    pause
    exit /b 1
)

echo.
echo [成功] 已设置每天 %START_TIME% 自动启动喝水提醒！
echo.
echo 说明：
echo   - 电脑需在 9:30 前已开机并登录
echo   - 若程序已在运行，不会重复打开
echo   - 取消自动启动请运行 uninstall_autostart.bat
echo.
pause
