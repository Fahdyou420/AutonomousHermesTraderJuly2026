# Hermes Trading Agent - System Auto-Start Controller
# Bootstraps the entire multi-service ecosystem (RPC, Docker stack, MCP server, dashboard)

$ErrorActionPreference = "Stop"

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "      HERMES TRADING INTEGRATION - DEPLOYMENT PIPELINE     " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""

$ExecutionPath = Get-Location
$VenvActivate  = Join-Path $ExecutionPath "hermes_rpc\.venv\Scripts\Activate.ps1"
$HostPython    = Join-Path $ExecutionPath "hermes_rpc\.venv\Scripts\python.exe"
if (-not (Test-Path $HostPython)) { $HostPython = "python" }

# 1. Start Hermes RPC Server (port 7778) - tool execution engine
Write-Host "[*] Initiating host-layer Python RPC services..." -ForegroundColor Yellow
if (Test-Path $VenvActivate) {
    $RpcCommand = "Set-Location '$ExecutionPath'; . '$VenvActivate'; uvicorn hermes_rpc.server:app --host 0.0.0.0 --port 7778 --reload"
} else {
    $RpcCommand = "Set-Location '$ExecutionPath'; uvicorn hermes_rpc.server:app --host 0.0.0.0 --port 7778 --reload"
}
try {
    Start-Process powershell.exe -ArgumentList "-NoExit","-NoProfile","-ExecutionPolicy","Bypass","-Command",$RpcCommand -WindowStyle Minimized
    Write-Host "[+] Hermes RPC Server launched on port 7778." -ForegroundColor Green
} catch {
    Write-Warning "[-] Could not start Hermes RPC. Run 'scripts\start_hermes_rpc.ps1' manually."
}

# 2. Start Trading MCP Server (port 7779) - exposes tools to Hermes Desktop Agent
Write-Host ""
Write-Host "[*] Launching Trading MCP Server (Hermes Desktop Agent connects here)..." -ForegroundColor Yellow
$McpCommand = "Set-Location '$ExecutionPath'; pip install yfinance uvicorn fastapi -q; python hermes_mcp_server.py"
try {
    Start-Process powershell.exe -ArgumentList "-NoExit","-NoProfile","-ExecutionPolicy","Bypass","-Command",$McpCommand -WindowStyle Minimized
    Write-Host "[+] Trading MCP Server launched on port 7779." -ForegroundColor Green
    Write-Host "    Register in Hermes Desktop: see hermes_config/config_block.yaml" -ForegroundColor Gray
} catch {
    Write-Warning "[-] Could not start MCP server. Run 'scripts\start_mcp_server.ps1' manually."
}

# 3. Spin up Docker containers
Write-Host ""
Write-Host "[*] Launching containerized microservices (Redis, ChromaDB, preprocessors, executors)..." -ForegroundColor Yellow
try {
    & docker-compose up -d
    Write-Host "[+] Docker containers started successfully." -ForegroundColor Green
} catch {
    Write-Error "[-] Failed to run docker-compose up. Ensure Docker Desktop is active."
    Exit 1
}

# 4. Wait for services to settle
Write-Host ""
Write-Host "[*] Allowing 15 seconds for database indexing and socket connections..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# 5. Build Obsidian directory structure
Write-Host ""
Write-Host "[*] Building and verifying local Obsidian knowledge vault..." -ForegroundColor Yellow
try {
    & $HostPython scripts/init_vault.py
} catch {
    Write-Warning "[-] Vault initialization warning: $_"
}

# 6. Open Dashboard in browser
Write-Host ""
Write-Host "[*] Opening trading dashboard..." -ForegroundColor Yellow
try {
    Start-Process "http://localhost:3000"
    Write-Host "[+] Dashboard open at http://localhost:3000" -ForegroundColor Green
} catch {
    Write-Host "[!] Navigate manually to http://localhost:3000" -ForegroundColor Yellow
}

# 7. Final status
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "         HERMES SYSTEM PIPELINES ARE NOW ONLINE          " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host " * Hermes RPC (tools)   :  [ON] -> http://localhost:7778" -ForegroundColor Green
Write-Host " * Trading MCP Server   :  [ON] -> http://localhost:7779/mcp" -ForegroundColor Cyan
Write-Host " * Redis                :  [ON] -> port 6379" -ForegroundColor Green
Write-Host " * ChromaDB             :  [ON] -> port 8000" -ForegroundColor Green
Write-Host " * MT5 Bridge           :  [ON] -> ZMQ port 5555 + HTTP 5558" -ForegroundColor Green
Write-Host " * Paper Trader         :  [ON] -> port 5561" -ForegroundColor Green
Write-Host " * Flask Dashboard      :  [ON] -> http://localhost:8080" -ForegroundColor Green
Write-Host " * React Dashboard      :  [ON] -> http://localhost:3000" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "NEXT STEP: Open Hermes Desktop Agent and add the MCP server:" -ForegroundColor Cyan
Write-Host "  See hermes_config/config_block.yaml for the exact config block." -ForegroundColor Cyan
Write-Host "  Then tell Hermes: 'Use the smc_trading_cycle skill, phase: scan'" -ForegroundColor Cyan
Write-Host ""
Write-Host "Stop everything: scripts\stop_all.ps1" -ForegroundColor Gray
