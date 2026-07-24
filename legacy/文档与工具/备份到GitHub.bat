@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo ========================================
echo   备份代码到 GitHub
echo ========================================
echo.

git -C "%~dp0\.." remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo 尚未连接 GitHub，请先看：文档与工具\GitHub连接教程.md
    pause
    exit /b 1
)

set /p COMMIT_MSG=本次修改说明 [默认: 更新代码]: 
if "%COMMIT_MSG%"=="" set COMMIT_MSG=更新代码

git -C "%~dp0\.." add .
git -C "%~dp0\.." commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo 没有新的改动需要提交。
) else (
    git -C "%~dp0\.." push
    if errorlevel 1 (
        echo 推送失败，请检查网络或 GitHub 登录。
        pause
        exit /b 1
    )
    echo [成功] 已同步到 https://github.com/lllll0912/-
)
pause
