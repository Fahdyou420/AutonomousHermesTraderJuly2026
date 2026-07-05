$ErrorActionPreference = 'Stop'
$taskName = 'HermesCron_ProofOfFire'
$log = 'C:\Users\user\Desktop\hermes_claude\HermesLogs\cron_proof_of_fire.log'
if(-not (Test-Path (Split-Path $log))){ New-Item -ItemType Directory -Path (Split-Path $log) -Force | Out-Null }
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoLogo -NoProfile -Command "Add-Content -Path ''{0}'' -Value ''[{0}] proof_of_fire_tick''' -f $log)
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Minutes 10)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User 'user' -Force
$task = Get-ScheduledTask -TaskName $taskName
'--- TASK ---'
$task | ConvertTo-Json -Depth 3
'--- TRIGGER ---'
$task.Triggers | ConvertTo-Json -Depth 3
