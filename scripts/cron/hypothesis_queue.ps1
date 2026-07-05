$ErrorActionPreference = 'SilentlyContinue'
$HermesCli = 'hermes'
$Workdir   = 'C:\Users\user\Desktop\hermes_claude'
$Prompt    = 'Check the R&D hypothesis queue at /data/rnd/queue.json (or wherever it currently resolves via RND_DATA_DIR). If any items have status: pending, pick the first one, run a backtest on it via the run_backtest skill, write results to 05_RND/results/, and update the queue item''s status to completed with a results reference.'
$Log       = Join-Path $Workdir 'HermesLogs\cron_hypothesis_queue.log'
if (-not (Test-Path (Split-Path $Log))) { New-Item -ItemType Directory -Path (Split-Path $Log) -Force | Out-Null }
Set-Location $Workdir
& $HermesCli -z $Prompt --skills run_backtest --workdir $Workdir *>&1 >> $Log
Add-Content -Path $Log -Value "[$(Get-Date -Format o)] hypothesis_queue_exit=$LASTEXITCODE"
