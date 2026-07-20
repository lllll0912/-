@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo === Configure GitHub Actions auto-deploy ===
echo 1. Open: https://github.com/lllll0912/-/settings/secrets/actions
echo 2. New repository secret
echo    Name:  FLY_API_TOKEN
echo    Value: open _token_once.txt and paste ALL text
echo 3. After saved, DELETE _token_once.txt
echo.
if exist "_token_once.txt" (
  start "" notepad "_token_once.txt"
) else (
  echo [!] _token_once.txt missing. Run:
  echo     flyctl tokens create deploy -a bill-private-lllll0912 -x 8760h
)
start "" "https://github.com/lllll0912/-/settings/secrets/actions"
pause
