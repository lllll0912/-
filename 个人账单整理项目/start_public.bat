@echo off
cd /d "%~dp0"

where cloudflared >nul 2>&1
if errorlevel 1 (
  echo [ERROR] cloudflared not found.
  echo Run: install_cloudflared.bat
  echo Or: winget install Cloudflare.cloudflared
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_tunnel.ps1"
if errorlevel 1 pause
pause