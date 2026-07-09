@echo off
chcp 65001 >nul
cd /d "%~dp0"

set GITHUB_USER=lllll0912
set REPO_NAME=-

echo ========================================
echo   推送到你的 GitHub: %GITHUB_USER%
echo ========================================
echo.
echo 请先在浏览器用你的账号登录并创建空仓库：
echo   https://github.com/new
echo   仓库名: %REPO_NAME%  （也可改成别的，改本脚本第6行）
echo   类型: Private 私有
echo   不要勾选 README
echo.
pause

git config user.name "%GITHUB_USER%"
git config user.email "%GITHUB_USER%@users.noreply.github.com"

git remote get-url origin >nul 2>&1
if not errorlevel 1 (
    git remote set-url origin https://github.com/%GITHUB_USER%/%REPO_NAME%.git
) else (
    git remote add origin https://github.com/%GITHUB_USER%/%REPO_NAME%.git
)

git branch -M main

echo.
echo 正在推送到 https://github.com/%GITHUB_USER%/%REPO_NAME%
echo 浏览器弹出时请登录 GitHub 账号: %GITHUB_USER%
echo.

git add .
git -c user.name="%GITHUB_USER%" -c user.email="%GITHUB_USER%@users.noreply.github.com" commit -m "更新项目与 GitHub 教程" 2>nul
git push -u origin main

if errorlevel 1 (
    echo.
    echo [失败] 请确认已在 GitHub 创建仓库，且浏览器登录的是 %GITHUB_USER%
    echo 若登错账号：凭据管理器删除 git:https://github.com 后重试
    pause
    exit /b 1
)

echo.
echo [成功] 已推送到你的 GitHub！
echo 地址: https://github.com/%GITHUB_USER%/%REPO_NAME%
pause
