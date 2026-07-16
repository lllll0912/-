@echo off
chcp 65001 >nul
echo 正在打开 Render Blueprint 部署页...
echo 仓库: https://github.com/lllll0912/-
echo.
start "" "https://dashboard.render.com/blueprint/new?repo=https%%3A%%2F%%2Fgithub.com%%2Flllll0912%%2F-&branch=main"
echo.
echo 请在打开的网页中：
echo   1. 用 GitHub 登录 Render（没有账号就注册免费版）
echo   2. 确认仓库为 lllll0912/- 
echo   3. 点击 Apply / Deploy Blueprint
echo   4. 等 daily-poem 变成 Live，复制 https://….onrender.com 链接
echo.
echo 完成后把链接发回给我，我帮你写进 README。
pause
