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
    npm install
    Pop-Location
}
if (-not (Test-Path data\recetary.db)) {
    Write-Host "Database not found — initializing..." -ForegroundColor Yellow
    & .\.venv\Scripts\recetary.exe init
}

$backendCmd = ".\.venv\Scripts\python.exe -m uvicorn recetary.main:app --reload --app-dir backend --port 8000"
$frontendCmd = "Set-Location frontend ; npm run dev"

Write-Host ""
Write-Host "Starting backend  → http://localhost:8000  (docs at /docs)" -ForegroundColor Green
Write-Host "Starting frontend → http://localhost:3000" -ForegroundColor Green
Write-Host ""

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$repoRoot' ; $backendCmd"
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$repoRoot' ; $frontendCmd"

Write-Host "Two terminal windows opened. Close them or press Ctrl+C inside each to stop." -ForegroundColor Cyan
