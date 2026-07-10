@echo off
chcp 65001 >nul
set REPO=%~dp0\..
cd /d "%REPO%"

REM 供计划任务静默调用，无窗口、无需输入
git remote get-url origin >nul 2>&1
if errorlevel 1 exit /b 0

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format \"yyyy-MM-dd HH:mm\""') do set TS=%%i

git add .
git diff --cached --quiet
if not errorlevel 1 exit /b 0

git -c user.name="lllll0912" -c user.email="lllll0912@users.noreply.github.com" commit -m "自动备份 %TS%"
if errorlevel 1 exit /b 0

git push
exit /b 0
