@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   同步到 GitHub
echo ========================================
echo.

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo 尚未连接 GitHub，请先运行 connect_github.bat
    pause
    exit /b 1
)

set /p COMMIT_MSG=请输入本次修改说明 [默认: 更新代码]: 
if "%COMMIT_MSG%"=="" set COMMIT_MSG=更新代码

git add .
git status -sb
echo.
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo 没有新的改动需要提交。
) else (
    git push
    if errorlevel 1 (
        echo 推送失败，请检查网络或 GitHub 登录状态。
        pause
        exit /b 1
    )
    echo.
    echo [成功] 已同步到 GitHub！
)
echo.
pause
