@echo off
chcp 65001 >nul
echo ========================================
echo  账单演示站上线（Netlify，无需绑卡）
echo ========================================
echo.
echo 1. 打开 https://app.netlify.com/drop
echo 2. 把文件夹 deploy-repo 拖进去
echo 3. 复制得到的 https://xxxx.netlify.app 链接
echo 4. 把链接发我，写入 README
echo.
start "" "https://app.netlify.com/drop"
start "" explorer "%~dp0deploy-repo"
pause
