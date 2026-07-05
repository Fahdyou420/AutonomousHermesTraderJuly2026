$ErrorActionPreference = 'Stop'
Register-ScheduledTask -TaskName 'HermesCron_MorningBriefing' `
  -Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoLogo -NoProfile -ExecutionPolicy Bypass -File C:\Users\user\Desktop\hermes_claude\scripts\cron\morning_briefing.ps1') `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 06:30) `
  -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable) `
  -User 'user' -Force | Out-Null
