$ErrorActionPreference = 'SilentlyContinue'
$HermesCli = 'hermes'
$Workdir   = 'C:\Users\user\Desktop\hermes_claude'
$Prompt    = 'Analyse today''s XAUUSD price action. Identify key levels broken, liquidity taken, FVGs formed. Write a market study note to the vault using the write_market_study skill. Update MEMORY.md with any new structural insights.'
$Log       = Join-Path $Workdir 'HermesLogs\cron_nightly_scan.log'
$DebugLog  = Join-Path $Workdir 'HermesLogs\cron_nightly_scan.debug.log'
if (-not (Test-Path (Split-Path $Log))) { New-Item -ItemType Directory -Path (Split-Path $Log) -Force | Out-Null }
Set-Location $Workdir
$timestamp = Get-Date -Format o
Add-Content -Path $Log -Value "[$timestamp] START"
# Capture stdout and stderr separately to a debug log
$p = Start-Process -FilePath $HermesCli -ArgumentList ('-z', $Prompt, '--skills', 'write_market_study', '--workdir', $Workdir) -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$Log.stdout.txt" -RedirectStandardError "$Log.stderr.txt"
Add-Content -Path $Log -Value "[$timestamp] EXIT=$($p.ExitCode)"
Add-Content -Path $DebugLog -Value "[$timestamp] nightly_scan exit=$($p.ExitCode)"
if(Test-Path "$Log.stdout.txt"){ Add-Content -Path $DebugLog -Value '--- STDOUT ---'; Add-Content -Path $DebugLog -Value (Get-Content "$Log.stdout.txt" -Raw); Remove-Item "$Log.stdout.txt" }
if(Test-Path "$Log.stderr.txt"){ Add-Content -Path $DebugLog -Value '--- STDERR ---'; Add-Content -Path $DebugLog -Value (Get-Content "$Log.stderr.txt" -Raw); Remove-Item "$Log.stderr.txt" }
