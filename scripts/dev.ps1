# Bring up Recetary for local development.
# Opens FastAPI (port 8000) and Next.js (port 3000) in separate windows so
# their logs stay visible. Press Ctrl+C in each window to stop.
#
# Usage from the repo root:  pwsh scripts\dev.ps1   (or  .\scripts\dev.ps1 )

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# Sanity checks
if (-not (Test-Path .venv\Scripts\python.exe)) {
    Write-Error "Python venv missing. Run: python -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -e backend[dev]"
}
if (-not (Test-Path frontend\node_modules)) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location frontend
    npm.cmd install
    Pop-Location
}
if (-not (Test-Path data\recetary.db)) {
    Write-Host "Database not found -- initializing..." -ForegroundColor Yellow
    & .\.venv\Scripts\recetary.exe init
}

$backendCmd = ".\.venv\Scripts\python.exe -m uvicorn recetary.main:app --reload --app-dir backend --port 8000"
$frontendCmd = "Set-Location frontend ; npm.cmd run dev"

# Read IMAGE_BACKEND from .env (same file the Python backend reads)
$imageBackend = "imagen"
if (Test-Path .env) {
    $match = Select-String -Path .env -Pattern '^\s*IMAGE_BACKEND\s*=\s*(.+)' | Select-Object -First 1
    if ($match) {
        $imageBackend = $match.Matches.Groups[1].Value.Trim().Trim('"').Trim("'").ToLower()
    }
}

Write-Host ""
Write-Host "Starting backend  -> http://localhost:8000  (docs at /docs)" -ForegroundColor Green
Write-Host "Starting frontend -> http://localhost:3000" -ForegroundColor Green
if ($imageBackend -eq "local") {
    Write-Host "Starting FLUX server -> http://localhost:8500" -ForegroundColor Green
}
Write-Host ""

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$repoRoot' ; $backendCmd"
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$repoRoot' ; $frontendCmd"

if ($imageBackend -eq "local") {
    $fluxCmd = ".\.venv\Scripts\python.exe backend\flux_server.py"
    Start-Sleep -Seconds 1
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$repoRoot' ; $fluxCmd"
}

$windowCount = if ($imageBackend -eq "local") { "Three" } else { "Two" }
Write-Host "$windowCount terminal windows opened. Close them or press Ctrl+C inside each to stop." -ForegroundColor Cyan
