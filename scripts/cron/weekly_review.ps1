$ErrorActionPreference = 'SilentlyContinue'
$HermesCli = 'hermes'
$Workdir   = 'C:\Users\user\Desktop\hermes_claude'
$Prompt    = 'Use the review_paper_trades skill to review all paper trades from the past 7 days. Compute win rate, expectancy, average R. Identify the best and worst setups. Update strategy cards in 02_STRATEGIES/active/.'
$Log       = Join-Path $Workdir 'HermesLogs\cron_weekly_review.log'
if (-not (Test-Path (Split-Path $Log))) { New-Item -ItemType Directory -Path (Split-Path $Log) -Force | Out-Null }
Set-Location $Workdir
& $HermesCli -z $Prompt --skills review_paper_trades --workdir $Workdir *>&1 >> $Log
Add-Content -Path $Log -Value "[$(Get-Date -Format o)] weekly_review_exit=$LASTEXITCODE"
