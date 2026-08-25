# 应急：本机喝水 JSON 盖到 Fly（会覆盖线上喝水记录！日常勿用）
# 日常请用 拉取线上数据到本机.ps1
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
Write-Host "WARNING: This OVERWRITES production water_data.json on Fly." -ForegroundColor Red
$confirm = Read-Host "Type YES to continue"
if ($confirm -ne "YES") {
    Write-Host "Aborted."
    exit 1
}
$local = ".\data\water_data.json"
if (-not (Test-Path $local)) {
    Write-Host "[ERROR] Missing $local" -ForegroundColor Red
    exit 1
}
Write-Host "Uploading water_data.json -> /data/water_data.json ..."
flyctl ssh sftp put $local "/data/water_data.json" --app bill-private-lllll0912
Write-Host "Done. Refresh https://bill-private-lllll0912.fly.dev/water/"
