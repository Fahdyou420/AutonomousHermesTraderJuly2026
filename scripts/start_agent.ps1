# start_agent.ps1
# Launches the Hermes Autonomous Trading Agent.
# Runs independently of MT5 - operates 24/7 on wall-clock time.
# On weekends it uses yfinance for price data instead of MT5.

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootPath   = Split-Path -Parent $ScriptPath
Set-Location $RootPath

Write-Host "==========================================================" -ForegroundColor Magenta
Write-Host "  HERMES AUTONOMOUS AGENT v2" -ForegroundColor Magenta
Write-Host "  Scan: 15min  Research: 4hr  Review: 24hr" -ForegroundColor Magenta
Write-Host "  Data: MT5 bridge (primary) + yfinance (weekend fallback)" -ForegroundColor Magenta
Write-Host "==========================================================" -ForegroundColor Magenta

if (Test-Path ".\venv\Scripts\Activate.ps1") { . .\venv\Scripts\Activate.ps1 }
elseif (Test-Path ".\.venv\Scripts\Activate.ps1") { . .\.venv\Scripts\Activate.ps1 }

$env:HERMES_INSTRUMENT  = "XAUUSD"
$env:HERMES_TIMEFRAME   = "M15"
$env:TRADING_MODE       = "paper"
$env:MAX_RISK_PCT       = "1.0"
$env:MAX_DAILY_DD       = "3.0"
$env:SCAN_INTERVAL_MIN  = "15"
$env:RESEARCH_INTERVAL_HR = "4"
$env:REVIEW_INTERVAL_HR   = "24"
$env:OLLAMA_URL         = "http://localhost:11434"
$env:MT5_BRIDGE_URL     = "http://localhost:5558"
$env:PAPER_TRADER_URL   = "http://localhost:5561"
$env:MCP_BRIDGE_URL     = "http://localhost:5562"
$env:BACKTESTER_URL     = "http://localhost:5560"
$env:OBSIDIAN_VAULT_ROOT = "C:\Fahd data AI\Fahd\Vault"

Write-Host "[*] Ensuring yfinance is installed (weekend data fallback)..." -ForegroundColor Yellow
pip install yfinance -q

Write-Host "[*] Waiting for Ollama..." -ForegroundColor Yellow
$waited = 0
while ($waited -lt 60) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($r.StatusCode -eq 200) { Write-Host "[OK] Ollama is online." -ForegroundColor Green; break }
    } catch { }
    Start-Sleep -Seconds 2
    $waited += 2
}

if ($waited -ge 60) {
    Write-Host "[!] Ollama did not respond. Is it running? Run: ollama serve" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Starting autonomous agent..." -ForegroundColor Green
Write-Host "     Logs: hermes_agent.log" -ForegroundColor Gray
Write-Host "     Stop: Ctrl+C" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Magenta
Write-Host ""

python -m hermes_rpc.autonomous_agent
