@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 同步 site 到 deploy-repo 并推送到 GitHub daily-poem ...
python scripts\build_poems_json.py
if errorlevel 1 exit /b 1
xcopy /Y /E /I site\* deploy-repo\
cd deploy-repo
git add .
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Update poems from poem.txt"
  git push origin main
  echo 已推送到 https://github.com/lllll0912/daily-poem
) else (
  echo 没有新的改动。
)
pause
