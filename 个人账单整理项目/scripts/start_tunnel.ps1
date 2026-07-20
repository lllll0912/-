# Start local bill app + Cloudflare quick tunnel.
# English-only console (avoids garbled Chinese in cmd.exe).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host ""
Write-Host "============================================"
Write-Host "  Personal Bills - Public Access (Tunnel)"
Write-Host "  Keep this window open. Lock screen OK."
Write-Host "  Do NOT sleep / shutdown."
Write-Host "============================================"
Write-Host ""

function Import-DotEnv {
    param([string]$Path)
    Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        $i = $line.IndexOf("=")
        if ($i -lt 1) { return }
        $name = $line.Substring(0, $i).Trim()
        $value = $line.Substring($i + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "Env:$name" $value
    }
}

function Write-DotEnv {
    param([string]$Password, [string]$Secret)
    @(
        "# Auto-generated. Do not commit."
        "BILL_ACCESS_PASSWORD=$Password"
        "BILL_SECRET_KEY=$Secret"
        "BILL_COOKIE_SECURE=1"
    ) | Set-Content -LiteralPath ".env" -Encoding UTF8
}

if (Test-Path ".env") {
    Import-DotEnv ".env"
}

$needPwd = $false
if (-not $env:BILL_ACCESS_PASSWORD) { $needPwd = $true }
elseif ($env:BILL_ACCESS_PASSWORD -match "换成你的|强密码|changeme|^password$|^123456$") { $needPwd = $true }

if ($needPwd) {
    Write-Host "[NEED PASSWORD] Type the password you want, then Enter:" -ForegroundColor Yellow
    $secure = Read-Host -AsSecureString
    $BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $pwd = [Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    }
    if ([string]::IsNullOrWhiteSpace($pwd)) {
        Write-Host "[ERROR] Empty password." -ForegroundColor Red
        exit 1
    }
    $secret = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
    Write-DotEnv -Password $pwd.Trim() -Secret $secret
    $env:BILL_ACCESS_PASSWORD = $pwd.Trim()
    $env:BILL_SECRET_KEY = $secret
    Write-Host "[OK] Password saved to .env" -ForegroundColor Green
} else {
    Write-Host "[OK] Password already set in .env" -ForegroundColor Green
}

if (-not $env:BILL_SECRET_KEY -or $env:BILL_SECRET_KEY -match "请换成|随机") {
    $env:BILL_SECRET_KEY = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
}
$env:BILL_COOKIE_SECURE = "1"
$env:HOST = "127.0.0.1"
$env:PORT = "8501"

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] cloudflared not found. Run install_cloudflared.bat first." -ForegroundColor Red
    exit 1
}

$venvPy = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host ">>> Creating .venv ..."
    python -m venv .venv
}
Write-Host ">>> Installing Python packages ..."
& $venvPy -m pip install -q -r requirements.txt

Write-Host ">>> Starting bill app on http://127.0.0.1:8501 ..."
$app = Start-Process -FilePath $venvPy -ArgumentList "app.py" -PassThru -WindowStyle Minimized `
    -WorkingDirectory (Get-Location)

Start-Sleep -Seconds 2
if ($app.HasExited) {
    Write-Host "[ERROR] Bill app failed to start. Try run.bat first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host ">>> Starting tunnel. Look for a line like:" -ForegroundColor Cyan
Write-Host "    https://XXXX.trycloudflare.com"
Write-Host "    Open it on phone -> login with your password."
Write-Host "    Ctrl+C to stop."
Write-Host ""

try {
    & cloudflared tunnel --url "http://127.0.0.1:8501"
}
finally {
    Write-Host ""
    Write-Host ">>> Stopping bill app ..."
    if ($app -and -not $app.HasExited) {
        Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
    }
}
