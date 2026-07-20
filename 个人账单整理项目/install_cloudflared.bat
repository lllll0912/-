@echo off
cd /d "%~dp0"
echo Installing Cloudflare cloudflared ...
winget install --id Cloudflare.cloudflared -e --accept-package-agreements --accept-source-agreements
echo.
echo Done. Then double-click: start_public.bat
pause