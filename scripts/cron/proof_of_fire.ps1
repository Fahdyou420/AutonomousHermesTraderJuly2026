$log = 'C:\Users\user\Desktop\hermes_claude\HermesLogs\cron_proof_of_fire.log'
Add-Content -Path $log -Value "[$(Get-Date -Format o)] proof_of_fire_tick"
