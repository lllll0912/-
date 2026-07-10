@echo off
chcp 65001 >nul

schtasks /Delete /TN "GitHub_AutoBackup_Noon" /F >nul 2>&1
schtasks /Delete /TN "GitHub_AutoBackup_Night" /F >nul 2>&1

echo 已取消 GitHub 定时自动备份。
pause
