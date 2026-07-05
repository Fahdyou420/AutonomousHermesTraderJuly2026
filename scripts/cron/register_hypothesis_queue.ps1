$ErrorActionPreference = 'Stop'
Register-ScheduledTask -TaskName 'HermesCron_HypothesisQueue' `
  -Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoLogo -NoProfile -ExecutionPolicy Bypass -File C:\Users\user\Desktop\hermes_claude\scripts\cron\hypothesis_queue.ps1') `
  -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 4) -RepetitionDuration (New-TimeSpan -Hours 24)) `
  -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable) `
  -User 'user' -Force | Out-Null
