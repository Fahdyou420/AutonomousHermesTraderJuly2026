# Hermes Trading Agent - System Auto-Stop Controller
# Halts all background containers and kills native uvicorn host service loops securely

$ErrorActionPreference = "Continue"

Write-Host "=========================================================" -ForegroundColor Red
Write-Host "     SHUTTING DOWN HERMES TRADING AUTONOMOUS STACK       " -ForegroundColor Red
Write-Host "=========================================================" -ForegroundColor Red
Write-Host ""

# 1. Stop docker-compose
Write-Host "[*] Dismantling container instances (databases and preprocessors)..." -ForegroundColor Yellow
try {
    & docker-compose down
    Write-Host "[+] Docker stack cleanly terminated and detached." -ForegroundColor Green
} catch {
    Write-Warning "[-] Error encountered during docker-compose down: $_"
}

# 2. Terminate the RPC Python Server (Uvicorn)
Write-Host ""
Write-Host "[*] Hunting local Windows uvicorn/python process gates..." -ForegroundColor Yellow

$KilledCount = 0

# Retrieve running processes representing uvicorn
$UvicornProcs = Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue
foreach ($p in $UvicornProcs) {
    try {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        Write-Host "  [-] Severed uvicorn socket thread [PID $($p.Id)]" -ForegroundColor DarkRed
        $KilledCount++
    } catch {}
}

# Scan running python processes for Hermes RPC characteristics 
$PythonProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue
foreach ($p in $PythonProcs) {
    try {
        # Check command line arguments to see if it belongs to hermes_rpc
        $CmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)").CommandLine
        if ($CmdLine -match "hermes_rpc" -or $CmdLine -match "server:app") {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            Write-Host "  [-] Severed Hermes Python Host process [PID $($p.Id)]" -ForegroundColor DarkRed
            $KilledCount++
        }
    } catch {}
}

if ($KilledCount -eq 0) {
    Write-Host "[i] No active host-level Hermes RPC server threads found." -ForegroundColor Gray
} else {
    Write-Host "[+] Successfully terminated $KilledCount host thread pipeline(s)." -ForegroundColor Green
}

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "         HERMES SYSTEM PIPELINES ARE SECURELY OFFLINE    " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
