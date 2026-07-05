$path = 'C:\Users\user\Desktop\hermes_claude\data\rnd\test_timer.log'
if (-not (Test-Path $path)) { New-Item -ItemType File -Path $path -Force | Out-Null }
Add-Content -LiteralPath $path -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz') + "`n")
