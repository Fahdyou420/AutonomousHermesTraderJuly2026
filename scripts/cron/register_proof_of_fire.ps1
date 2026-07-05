$ErrorActionPreference = 'Stop'
$taskName = 'HermesCron_ProofOfFire'
$payload = @'
$log = 'C:\Users\user\Desktop\hermes_claude\HermesLogs\cron_proof_of_fire.log'
Add-Content -Path $log -Value "[$(Get-Date -Format o)] proof_of_fire_tick"
'@
$scriptPath = 'C:\Users\user\Desktop\hermes_claude\scripts\cron\proof_of_fire.ps1'
Set-Content -Path $scriptPath -Value $payload -Encoding UTF8

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoLogo -NoProfile -ExecutionPolicy Bypass -Command "& ''{0}''"' -f $scriptPath)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration ([TimeSpan]::MaxValue)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User 'user' -Force | Format-List
Get-ScheduledTask -TaskName $taskName | Format-List
