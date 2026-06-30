# start_hermes_rpc.ps1
# PowerShell script to run the Hermes Host RPC Server on Windows.
# This server facilitates file, ledger editing, vector retrieval, calendar scraping, and ZeroMQ execution pipelines.

# Resolve absolute execution path location
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptPath
# Move up to root project folder containing hermes_rpc
Set-Location ..

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Hermes Autonomous AI Trading System - Windows RPC Server " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Look for Python Virtual Environments and activate if found
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "[*] Activating Python local virtual environment (venv)..." -ForegroundColor Yellow
    . .\venv\Scripts\Activate.ps1
} elseif (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "[*] Activating Python local virtual environment (.venv)..." -ForegroundColor Yellow
    . .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "[!] No virtual environment folders detected at root. Proceeding with global python..." -ForegroundColor Gray
}

# 2. Check for dependencies setup
Write-Host "[*] Verifying/installing dependencies from hermes_rpc/requirements.txt..." -ForegroundColor Yellow
python -m pip install -r .\hermes_rpc\requirements.txt --quiet

# 3. Startup the RPC application server
Write-Host "[OK] Starting Hermes RPC Server. Binding to 0.0.0.0:7778..." -ForegroundColor Green
Write-Host "    Stop the server anytime using Ctrl + C." -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan

uvicorn hermes_rpc.server:app --host 0.0.0.0 --port 7778 --reload
