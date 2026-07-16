@echo off
chcp 65001 >nul
echo ========================================
echo  每日一诗 — 不依赖选仓库的上线方式
echo ========================================
echo.
echo [1] 打开 Netlify 拖拽页（最快拿到链接）
echo [2] 打开已准备好的站点文件夹（拖进 Netlify）
echo [3] 打开 GitHub 新建 daily-poem 仓库
echo [4] 打开「选不到仓库时」说明
echo [0] 退出
echo.
set /p c=请选择：
if "%c%"=="1" start "" "https://app.netlify.com/drop"
if "%c%"=="2" start "" explorer "%~dp0deploy-repo"
if "%c%"=="3" start "" "https://github.com/new?name=daily-poem&visibility=public"
if "%c%"=="4" start "" notepad "%~dp0选不到仓库时.md"
if "%c%"=="0" exit /b 0
pause
