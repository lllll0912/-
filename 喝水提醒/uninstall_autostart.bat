@echo off
chcp 65001 >nul

set TASK_NAME=HydroPulse_WaterReminder

echo 正在移除每日自动启动计划任务...
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

if errorlevel 1 (
    echo 未找到计划任务，或删除失败。
) else (
    echo 已取消每天自动启动。
)
pause
