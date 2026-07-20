@echo off
chcp 65001 >nul
echo ========================================
echo  账单演示站 — Netlify 连接 GitHub
echo ========================================
echo.
echo 仓库已推送: https://github.com/lllll0912/bill-demo
echo.
echo Netlify 设置：
echo   1. https://app.netlify.com → Add new site → Import an existing project
echo   2. 选 GitHub → 仓库 bill-demo
echo   3. Branch: main
echo   4. Build command: 留空
echo   5. Publish directory: 留空（或 .）
echo   6. Deploy
echo.
echo 若列表没有 bill-demo：
echo   https://github.com/settings/installations → Netlify → 勾选 bill-demo
echo.
start "" "https://app.netlify.com/start"
start "" "https://github.com/lllll0912/bill-demo"
pause
