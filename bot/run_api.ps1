# Start the API server locally using the project virtual environment.
$ErrorActionPreference = "Stop"

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "❌ Missing .venv interpreter at $venvPython"
    Write-Host "   Create it first: py -3 -m venv .venv"
    Write-Host "   Then install deps: .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

Write-Host "🚀 Starting dYdX Trading Bot API Server..."
Write-Host "📊 Dashboard will be available at: http://localhost:8889"
Write-Host "📖 API Documentation available at: http://localhost:8889/docs"
Write-Host "🔍 Health check available at: http://localhost:8889/health"
Write-Host ""

& $venvPython (Join-Path $PSScriptRoot "start_api.py")

