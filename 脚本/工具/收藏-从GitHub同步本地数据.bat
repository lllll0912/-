@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0..\.."

echo 从 origin/main 拉取收藏运行态到本机（仅工作区，不参与 commit）...
git fetch origin
if errorlevel 1 (
  echo fetch 失败
  exit /b 1
)

echo 临时取消 skip-worktree 以便检出...
python -c "import subprocess; paths=[p for p in subprocess.check_output(['git','ls-files','-z','--','收藏/数据/pics','收藏/数据/_meta/catalog.json','收藏/数据/_meta/lookup_cache.json']).split(b'\0') if p];
[subprocess.run(['git','update-index','--no-skip-worktree','--']+paths[i:i+50], check=False) for i in range(0,len(paths),50)]; print('cleared', len(paths))"

git checkout origin/main -- "收藏/数据/pics" "收藏/数据/_meta/catalog.json" "收藏/数据/_meta/lookup_cache.json" 2>nul
if errorlevel 1 (
  echo 部分路径在远端不存在，可忽略
)

echo 重新设置 skip-worktree...
python -c "import subprocess; paths=[p for p in subprocess.check_output(['git','ls-files','-z','--','收藏/数据/pics','收藏/数据/_meta/catalog.json','收藏/数据/_meta/lookup_cache.json','收藏/数据/_meta/pics_index.json']).split(b'\0') if p];
[subprocess.run(['git','update-index','--skip-worktree','--']+paths[i:i+50], check=False) for i in range(0,len(paths),50)];
[subprocess.run(['git','update-index','--no-skip-worktree','--',p], check=False) for p in ['收藏/数据/pics/.gitkeep','收藏/数据/_meta/.gitkeep','收藏/数据/_meta/catalog.empty.json']];
print('skip-worktree set on', len(paths), 'files')"

echo.
echo 完成。本机数据已与远端对齐，且不会被误 push。
pause
