# 手动应急部署（正常应 git push → GitHub Action 自动 deploy）
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
Write-Host "Manual deploy fallback. Prefer: git push origin main"
flyctl deploy --app bill-private-lllll0912 --remote-only
