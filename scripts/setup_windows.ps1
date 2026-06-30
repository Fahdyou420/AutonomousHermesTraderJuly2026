# Hermes Trading Agent - Windows Host Environment Setup
# This PowerShell script prepares your Windows environment for the Hermes Trading Agent system.

$ErrorActionPreference = "Stop"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   HERMES TRADING AGENT SYSTEM INSTALLER     " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check if Python 3.11 is installed
Write-Host "[*] Checking Python 3.11 installation..." -ForegroundColor Yellow
try {
    $pythonVerOutput = & python --version 2>&1
    if ($pythonVerOutput -match "Python 3\.11\.") {
        Write-Host "[+] Python 3.11 identified successfully: $pythonVerOutput" -ForegroundColor Green
    } else {
        Write-Warning "[-] Python version is not 3.11. Found: $pythonVerOutput"
        Write-Warning "[-] It is highly recommended to install Python 3.11.x to ensure MT5 and core RPC compatibility."
    }
} catch {
    Write-Error "[-] Python is not installed or not added to your PATH environment. Please install Python 3.11."
    Exit 1
}

# 2. Check and Create Virtual Environment
Write-Host ""
Write-Host "[*] Creating Python Virtual Environment at ./hermes_rpc/.venv ..." -ForegroundColor Yellow
$VenvPath = Join-Path (Get-Location) "hermes_rpc\.venv"

if (Test-Path $VenvPath) {
    Write-Host "[+] Virtual environment already exists at $VenvPath. Overstepping creation." -ForegroundColor Gray
} else {
    try {
        & python -m venv hermes_rpc\.venv
        Write-Host "[+] Virtual environment created successfully." -ForegroundColor Green
    } catch {
        Write-Error "[-] Failed to create python virtual environment: $_"
        Exit 1
    }
}

# 3. Pip Install requirements.txt
Write-Host ""
Write-Host "[*] Installing Hermes RPC Server dependencies..." -ForegroundColor Yellow
$PipPath = Join-Path $VenvPath "Scripts\pip.exe"

if (-not (Test-Path $PipPath)) {
    Write-Error "[-] pip executable not found at expected path: $PipPath"
    Exit 1
}

try {
    Write-Host "[*] Executing pip install. This might take a dynamic minute..." -ForegroundColor Gray
    # Run pip directly to avoid activation overheads
    & $PipPath install --upgrade pip
    & $PipPath install -r hermes_rpc/requirements.txt
    Write-Host "[+] Hermes RPC Server dependencies installed successfully." -ForegroundColor Green
} catch {
    Write-Error "[-] Failed to install python packages: $_"
    Exit 1
}

# 4. Copying config files to $env:USERPROFILE\.hermes
Write-Host ""
Write-Host "[*] Deploying Hermes configuration files..." -ForegroundColor Yellow
$HermesHome = Join-Path $env:USERPROFILE ".hermes"
$HermesSkills = Join-Path $HermesHome "skills\trading"

# Create directories
if (-not (Test-Path $HermesHome)) {
    New-Item -ItemType Directory -Force -Path $HermesHome | Out-Null
    Write-Host "[+] Created folder: $HermesHome" -ForegroundColor Green
}
if (-not (Test-Path $HermesSkills)) {
    New-Item -ItemType Directory -Force -Path $HermesSkills | Out-Null
    Write-Host "[+] Created folder: $HermesSkills" -ForegroundColor Green
}

# Copy markdown documents
$ConfigFiles = @{
    "hermes_config\AGENTS.md" = Join-Path $HermesHome "AGENTS.md"
    "hermes_config\SOUL.md"   = Join-Path $HermesHome "SOUL.md"
    "hermes_config\MEMORY.md" = Join-Path $HermesHome "MEMORY.md"
}

foreach ($src in $ConfigFiles.Keys) {
    $dest = $ConfigFiles[$src]
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dest -Force
        Write-Host "[+] Copied $src -> $dest" -ForegroundColor Green
    } else {
        Write-Warning "[-] Source file not found: $src"
    }
}

# Copy all skills `.md` files to $env:USERPROFILE\.hermes\skills\trading\
$SkillsSourcePath = "hermes_config\skills"
if (Test-Path $SkillsSourcePath) {
    $skills = Get-ChildItem -Path $SkillsSourcePath -Filter "*.md"
    foreach ($skill in $skills) {
        $destFile = Join-Path $HermesSkills $skill.Name
        Copy-Item -Path $skill.FullName -Destination $destFile -Force
        Write-Host "  [+] Copied skill: $($skill.Name)" -ForegroundColor Green
    }
} else {
    Write-Warning "[-] Skills config directory not found: $SkillsSourcePath"
}

# 5. Create local data/ folder structure
Write-Host ""
Write-Host "[*] Provisioning local data files storage layers..." -ForegroundColor Yellow
$DataFolders = @(
    "data",
    "data\obsidian",
    "data\logs",
    "data\backtests",
    "data\market_data"
)

foreach ($folder in $DataFolders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Force -Path $folder | Out-Null
        Write-Host "[+] Created folder: $folder" -ForegroundColor Green
    } else {
        Write-Host "[+] Folder already exists: $folder" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "[*] Configuring Windows Firewall rules for Hermes ports..." -ForegroundColor Yellow
$FirewallRules = @(
    @{ Name = "Hermes RPC 7778";      Port = 7778 },
    @{ Name = "Hermes ZMQ Data 5555"; Port = 5555 },
    @{ Name = "Hermes ZMQ Draw 5556"; Port = 5556 },
    @{ Name = "Hermes ZMQ Order 5557";Port = 5557 }
)
foreach ($rule in $FirewallRules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if (-not $existing) {
        New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Protocol TCP -LocalPort $rule.Port -Action Allow | Out-Null
        Write-Host "[+] Firewall rule added: $($rule.Name) (port $($rule.Port))" -ForegroundColor Green
    } else {
        Write-Host "[+] Firewall rule already exists: $($rule.Name)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Green
Write-Host "       HERMES WINDOWS SETUP CONCLUDED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Green
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Configure your local '.env' file with correct keys and absolute paths."
Write-Host "2. Install/Open MetaTrader 5 terminal and compile the Hermes EA."
Write-Host "3. Run 'scripts/start_all.ps1' to spin up the RPC server, database, and system containerized microservices."
Write-Host "==========================================================================" -ForegroundColor Green
