# 从 Fly Volume 拉取线上类型字典到本机 data/category_rules.json
# 开发前建议先跑一遍，再本地改功能 / 测试 / 推送（字典本身已持久在 Volume，推代码不会盖掉）
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))

$app = "bill-private-lllll0912"
$destDir = ".\data"
$dest = Join-Path $destDir "category_rules.json"
New-Item -ItemType Directory -Force -Path $destDir | Out-Null

Write-Host "Downloading /data/category_rules.json from Fly ($app) ..."
flyctl ssh sftp get "/data/category_rules.json" $dest --app $app
if (-not (Test-Path $dest)) {
    Write-Host "[WARN] Volume 上可能还没有该文件（首次迁移前）。可改从备份恢复：" -ForegroundColor Yellow
    Write-Host "  .\\.venv\\Scripts\\python.exe tools\\sync_rules_from_backup.py"
    exit 1
}
Write-Host "[OK] Saved to $dest"
Write-Host "本地开发请直接用 run.bat；改字典也会写到 data/，不会被 git push 覆盖线上 Volume。"
