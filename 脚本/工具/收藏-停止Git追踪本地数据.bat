@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0..\.."

echo 对本机已追踪的收藏运行态设置 skip-worktree（不删远端文件）
echo 效果：本地改 pics/catalog 不会出现在 git status，也不会被 commit 盖掉 GitHub
echo.

python -c "import subprocess; paths=[p for p in subprocess.check_output(['git','ls-files','-z','--','收藏/数据/pics','收藏/数据/_meta/catalog.json','收藏/数据/_meta/lookup_cache.json','收藏/数据/_meta/pics_index.json']).split(b'\0') if p];
[subprocess.run(['git','update-index','--skip-worktree','--']+paths[i:i+50], check=False) for i in range(0,len(paths),50)];
print('skip-worktree set on', len(paths), 'files')"

for %%F in ("收藏\数据\pics\.gitkeep" "收藏\数据\_meta\.gitkeep" "收藏\数据\_meta\catalog.empty.json") do (
  git update-index --no-skip-worktree -- "%%~F" 2>nul
)

echo.
echo 完成。远端 GitHub 上的 pics/catalog 保持不动；本机仅作测试数据。
pause
