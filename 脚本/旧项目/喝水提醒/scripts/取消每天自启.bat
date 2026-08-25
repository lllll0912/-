@echo off
chcp 65001 >nul

set TASK_NAME=HydroPulse_WaterReminder
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1
echo 已取消每天自动启动。
pause
