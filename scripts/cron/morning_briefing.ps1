$ErrorActionPreference = 'SilentlyContinue'
$HermesCli = 'hermes'
$Workdir   = 'C:\Users\user\Desktop\hermes_claude'
$Prompt    = 'Fetch the economic calendar for today. Check XAUUSD overnight structure using the analyse_market_structure skill. Assess London open bias. Write a briefing note to 00_INBOX/.'
$Log       = Join-Path $Workdir 'HermesLogs\cron_morning_briefing.log'
if (-not (Test-Path (Split-Path $Log))) { New-Item -ItemType Directory -Path (Split-Path $Log) -Force | Out-Null }
Set-Location $Workdir
& $HermesCli -z $Prompt --skills analyse_market_structure --workdir $Workdir *>&1 >> $Log
Add-Content -Path $Log -Value "[$(Get-Date -Format o)] morning_briefing_exit=$LASTEXITCODE"
