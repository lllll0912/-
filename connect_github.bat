@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   连接 GitHub 远程仓库（首次使用）
echo ========================================
echo.
echo 请先在浏览器创建空仓库: https://github.com/new
echo 建议选 Private（私有），不要添加 README。
echo.

set /p GITHUB_USER=请输入你的 GitHub 用户名: 
if "%GITHUB_USER%"=="" (
    echo 用户名不能为空。
    pause
    exit /b 1
)

set /p REPO_NAME=请输入仓库名 [默认: cursor-projects]: 
if "%REPO_NAME%"=="" set REPO_NAME=cursor-projects

echo.
echo 将连接到: https://github.com/%GITHUB_USER%/%REPO_NAME%
echo.

git remote get-url origin >nul 2>&1
if not errorlevel 1 (
    echo 已存在远程 origin，正在更新地址...
    git remote set-url origin https://github.com/%GITHUB_USER%/%REPO_NAME%.git
) else (
    git remote add origin https://github.com/%GITHUB_USER%/%REPO_NAME%.git
)

git branch -M main

echo 正在推送到 GitHub（首次可能需要浏览器登录）...
git push -u origin main

if errorlevel 1 (
    echo.
    echo [提示] 推送失败常见原因：
    echo   1. GitHub 上还没创建该仓库
    echo   2. 未登录 GitHub（可运行: git credential manager 或安装 GitHub Desktop）
    echo   3. 仓库名或用户名填错
    pause
    exit /b 1
)

echo.
echo [成功] 已连接并推送到 GitHub！
echo 以后修改代码后，运行 sync_github.bat 即可备份。
echo.
pause
