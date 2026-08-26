@echo off
chcp 65001 >nul
cd /d "%~dp0..\..\.."

where flyctl >nul 2>&1 || (
  echo [!] 未找到 flyctl，请先安装 Fly CLI
  pause
  exit /b 1
)

echo.
echo === 把 GitHub token 写入 Fly（HEALTH_GITHUB_TOKEN）===
echo 用途：手机在正式站上传医疗材料时，自动 commit 进私密仓库
echo.
echo 请粘贴 token（github_pat_... 或 ghp_...），回车后不会显示：
set /p TOKEN=

if "%TOKEN%"=="" (
  echo [!] 未输入 token
  pause
  exit /b 1
)

flyctl secrets set "HEALTH_GITHUB_TOKEN=%TOKEN%" -a bill-private-lllll0912
set TOKEN=
echo.
echo 已提交到 Fly，机器会短暂重启。上传页应显示「自动写入 GitHub」。
pause
