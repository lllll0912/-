# 手动应急：把本机 data/bills.db 盖到 Fly（日常以云端为准，一般不用）
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
if (-not (Test-Path ".\data\bills.db")) {
    Write-Host "[ERROR] Missing .\data\bills.db" -ForegroundColor Red
    exit 1
}
Write-Host "Uploading as /data/bills_restored.db ..."
flyctl ssh sftp put ".\data\bills.db" "/data/bills_restored.db" --app bill-private-lllll0912
$mid = (flyctl machines list --app bill-private-lllll0912 --json | ConvertFrom-Json)[0].id
flyctl machine exec $mid --app bill-private-lllll0912 "sh -c 'rm -f /data/bills.db /data/bills.db-wal /data/bills.db-shm; mv /data/bills_restored.db /data/bills.db'"
flyctl machines restart $mid --app bill-private-lllll0912
Write-Host "Done. https://bill-private-lllll0912.fly.dev"
