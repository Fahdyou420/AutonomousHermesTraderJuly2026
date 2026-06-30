# start_mcp_server.ps1
# Launches the Hermes Trading MCP Server on port 7779.
# The Hermes Desktop Agent connects to this to call trading tools.
# Run after docker compose is up.

$RootPath = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootPath

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  HERMES TRADING MCP SERVER - port 7779" -ForegroundColor Cyan
Write-Host "  Hermes Agent calls trading tools through here" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (Test-Path ".\venv\Scripts\Activate.ps1") { . .\venv\Scripts\Activate.ps1 }
elseif (Test-Path ".\.venv\Scripts\Activate.ps1") { . .\.venv\Scripts\Activate.ps1 }

$env:MT5_BRIDGE_URL    = "http://localhost:5558"
$env:PAPER_TRADER_URL  = "http://localhost:5561"
$env:PREPROCESSOR_URL  = "http://localhost:5559"
$env:BACKTESTER_URL    = "http://localhost:5560"
$env:MCP_BRIDGE_URL    = "http://localhost:5562"
$env:MCP_TRADING_PORT  = "7779"

pip install yfinance uvicorn fastapi -q

Write-Host "[OK] Starting on http://localhost:7779/mcp" -ForegroundColor Green
Write-Host "     Config: see hermes_config/config_block.yaml" -ForegroundColor Gray
Write-Host ""

python hermes_mcp_server.py
