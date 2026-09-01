@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0..\.."
echo 设置本机运行态 skip-worktree（不删 GitHub 远端文件）...
python "脚本\工具\skip_worktree_runtime_data.py"
echo.
echo 完成。正式站 Volume + 日备 backups/ 不受影响。
pause
