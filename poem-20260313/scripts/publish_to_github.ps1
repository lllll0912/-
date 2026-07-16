# Publish daily-poem to GitHub (run after code changes)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Deploy = Join-Path $Root "deploy-repo"

Set-Location $Root
Write-Host ">> build poems.json"
python (Join-Path $Root "scripts\build_poems_json.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ">> sync deploy-repo"
Copy-Item -Path (Join-Path $Root "site\*") -Destination $Deploy -Recurse -Force

Set-Location $Deploy
git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  git commit -m "Update daily-poem site"
  git push origin main
  Write-Host ">> pushed daily-poem"
} else {
  Write-Host ">> daily-poem unchanged"
}

Set-Location (Split-Path -Parent $Root)
git add poem-20260313/
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  git commit -m "Update poem-20260313 project files"
  git push origin main
  Write-Host ">> pushed monorepo"
} else {
  Write-Host ">> monorepo unchanged"
}

Write-Host ">> done"
