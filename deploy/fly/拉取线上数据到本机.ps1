# 从 Fly Volume 拉「线上数据」到本机 data/（只读云端 → 本机，不改线上）
# 用途：本地开发要对齐线上已有账单/字典/喝水时用。不会上传、不会部署覆盖。
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))

$app = "bill-private-lllll0912"
$destDir = ".\data"
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $destDir "notes_assets") | Out-Null

Write-Host "=== Pull FROM Fly ($app) /data -> local .\data  (cloud unchanged) ===" -ForegroundColor Cyan

function Pull-One($remote, $local) {
    Write-Host "get $remote -> $local"
    try {
        flyctl ssh sftp get $remote $local --app $app
    } catch {
        Write-Host "  [skip] $remote ($($_.Exception.Message))" -ForegroundColor Yellow
    }
}

Pull-One "/data/bills.db" (Join-Path $destDir "bills.db")
Pull-One "/data/category_rules.json" (Join-Path $destDir "category_rules.json")
Pull-One "/data/water_data.json" (Join-Path $destDir "water_data.json")
Pull-One "/data/notes.db" (Join-Path $destDir "notes.db")

Write-Host ""
Write-Host "[OK] 本机 data/ 已尽量对齐线上。用 run.bat 测即可。"
Write-Host "注意：之后本地改的 data/ 不会自动上云；git push 也只更代码，不会把本机库盖到线上。"
Write-Host "诗词在 /data/poems/，体积可能较大；需要时再单独 sftp 拉取。"
