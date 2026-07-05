$ErrorActionPreference = 'Stop'
Register-ScheduledTask -TaskName 'HermesCron_NightlyScan' `
  -Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoLogo -NoProfile -ExecutionPolicy Bypass -File C:\Users\user\Desktop\hermes_claude\scripts\cron\nightly_scan.ps1') `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 22:00) `
  -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable) `
  -User 'user' -Force | Out-Null
