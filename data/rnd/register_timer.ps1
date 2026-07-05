$ErrorActionPreference='Stop'
$action=New-ScheduledTaskAction -Execute 'C:\Python314\python.exe' -Argument '-c "import datetime; p=open('\''C:\Users\user\Desktop\hermes_claude\data\rnd\test_timer.log'\'','\''a'\'',encoding='\''ascii'\''); p.write(datetime.datetime.now().strftime('\''%Y-%m-%d %H:%M:%S %z'\'')+'\''\n'\''); p.flush(); p.close()"'
$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(10) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration ([TimeSpan]::MaxValue)
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName 'HermesTimerProof' -Action $action -Trigger $trigger -Settings $settings -Force | Format-List
