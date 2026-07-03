# start_mcp_server.ps1
# Launches the Hermes Trading MCP Server on port 7779.
# The Hermes Desktop Agent connects to this to call trading tools.
# Run after docker compose is up.
#
# All configuration is loaded from .env in the project root.
# Copy .env.example to .env and edit it to change vault path, models,
# risk limits, log location, or any service URL.

$RootPath = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootPath

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  HERMES TRADING MCP SERVER - port 7779" -ForegroundColor Cyan
Write-Host "  Hermes Agent calls trading tools through here" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (Test-Path ".\venv\Scripts\Activate.ps1") { . .\venv\Scripts\Activate.ps1 }
elseif (Test-Path ".\.venv\Scripts\Activate.ps1") { . .\.venv\Scripts\Activate.ps1 }

#  Load .env if present 
$envFile = Join-Path $RootPath ".env"
if (Test-Path $envFile) {
    Write-Host "[*] Loading configuration from .env..." -ForegroundColor Yellow
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line -split "=", 2
            $key = $parts[0].Trim()
            $val = $parts[1].Trim()
            if ($val) {
                [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
            }
        }
    }
    Write-Host "[+] .env loaded." -ForegroundColor Green
} else {
    Write-Host "[!] No .env found. Using defaults. Copy .env.example to .env to customize." -ForegroundColor Yellow
}

#  Defaults for anything not set in .env 
if (-not $env:MT5_BRIDGE_URL)      { $env:MT5_BRIDGE_URL     = "http://localhost:5558" }
if (-not $env:PAPER_TRADER_URL)    { $env:PAPER_TRADER_URL   = "http://localhost:5561" }
if (-not $env:PREPROCESSOR_URL)    { $env:PREPROCESSOR_URL   = "http://localhost:5559" }
if (-not $env:BACKTESTER_URL)      { $env:BACKTESTER_URL     = "http://localhost:5560" }
if (-not $env:MCP_BRIDGE_URL)      { $env:MCP_BRIDGE_URL     = "http://localhost:5562" }
if (-not $env:MCP_TRADING_PORT)    { $env:MCP_TRADING_PORT   = "7779" }
if (-not $env:HERMES_HOME_DIR)     { $env:HERMES_HOME_DIR    = "$env:USERPROFILE\.hermes" }
if (-not $env:HERMES_SKILLS_DIR)   { $env:HERMES_SKILLS_DIR  = "$env:USERPROFILE\.hermes\skills\trading" }
if (-not $env:OBSIDIAN_VAULT_ROOT) { $env:OBSIDIAN_VAULT_ROOT = "$env:LOCALAPPDATA\hermes\obsidian" }
if (-not $env:HERMES_LOG_DIR)      { $env:HERMES_LOG_DIR     = "$env:USERPROFILE\HermesLogs" }
if (-not $env:HERMES_INSTRUMENT)   { $env:HERMES_INSTRUMENT  = "XAUUSD" }
if (-not $env:MAX_RISK_PCT)        { $env:MAX_RISK_PCT       = "1.0" }
if (-not $env:MAX_DAILY_DD)        { $env:MAX_DAILY_DD       = "3.0" }

pip install yfinance uvicorn fastapi -q

Write-Host ""
Write-Host "[*] Configuration:" -ForegroundColor Cyan
Write-Host "    Vault:      $env:OBSIDIAN_VAULT_ROOT" -ForegroundColor Gray
Write-Host "    Skills:     $env:HERMES_SKILLS_DIR" -ForegroundColor Gray
Write-Host "    Logs:       $env:HERMES_LOG_DIR" -ForegroundColor Gray
Write-Host "    Instrument: $env:HERMES_INSTRUMENT" -ForegroundColor Gray
Write-Host "    Max risk:   $env:MAX_RISK_PCT%  |  Daily DD halt: $env:MAX_DAILY_DD%" -ForegroundColor Gray
Write-Host ""
Write-Host "[OK] Starting on http://localhost:7779/mcp" -ForegroundColor Green
Write-Host ""

python hermes_mcp_server.py
