@echo off
chcp 65001 >nul
echo ========================================
echo  每日一诗 — 连接 Render（仓库 daily-poem）
echo ========================================
echo.
echo 源码已推送到: https://github.com/lllll0912/daily-poem
echo.
echo 正在打开 Render 新建静态站页面...
start "" "https://dashboard.render.com/static/new"
echo.
echo 在网页中按下面填写：
echo   Repository     : lllll0912 / daily-poem
echo   Branch         : main
echo   Name           : daily-poem
echo   Root Directory : （留空）
echo   Build Command  : true
echo   Publish Dir    : .
echo.
echo 若列表里没有 daily-poem：
echo   https://github.com/settings/installations
echo   → Render → Configure → 勾选 daily-poem → Save
echo.
echo 部署成功后把 https://….onrender.com 链接发给我。
pause
