# 把本机 data/water_data.json 同步到 Fly Volume（/data/water_data.json）
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
$local = ".\data\water_data.json"
if (-not (Test-Path $local)) {
    Write-Host "[ERROR] Missing $local" -ForegroundColor Red
    exit 1
}
Write-Host "Uploading water_data.json -> /data/water_data.json ..."
flyctl ssh sftp put $local "/data/water_data.json" --app bill-private-lllll0912
Write-Host "Done. Refresh https://bill-private-lllll0912.fly.dev/water/"
