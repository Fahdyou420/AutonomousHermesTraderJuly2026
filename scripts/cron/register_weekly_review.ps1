$ErrorActionPreference = 'Stop'
Register-ScheduledTask -TaskName 'HermesCron_WeeklyReview' `
  -Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoLogo -NoProfile -ExecutionPolicy Bypass -File C:\Users\user\Desktop\hermes_claude\scripts\cron\weekly_review.ps1') `
  -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 08:00) `
  -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable) `
  -User 'user' -Force | Out-Null
