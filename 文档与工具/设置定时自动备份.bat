@echo off
chcp 65001 >nul
cd /d "%~dp0"

set SCRIPT=%~dp0自动备份到GitHub.bat

echo ========================================
echo   设置 GitHub 定时自动备份
echo ========================================
echo.
echo 计划：每天 12:00 和 21:00 自动推送到 GitHub
echo 仓库：https://github.com/lllll0912/-
echo.

schtasks /Delete /TN "GitHub_AutoBackup_Noon" /F >nul 2>&1
schtasks /Delete /TN "GitHub_AutoBackup_Night" /F >nul 2>&1

schtasks /Create /TN "GitHub_AutoBackup_Noon" /TR "\"%SCRIPT%\"" /SC DAILY /ST 12:00 /IT /F
schtasks /Create /TN "GitHub_AutoBackup_Night" /TR "\"%SCRIPT%\"" /SC DAILY /ST 21:00 /IT /F

if errorlevel 1 (
    echo [失败] 创建计划任务失败。
    pause
    exit /b 1
)

echo [成功] 已开启定时自动备份！
echo   - 每天 12:00 推送一次
echo   - 每天 21:00 推送一次
echo   - 无改动时自动跳过
echo.
echo 取消请运行：取消定时自动备份.bat
pause
