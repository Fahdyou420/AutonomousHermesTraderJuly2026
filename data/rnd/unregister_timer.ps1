try { Unregister-ScheduledTask -TaskName 'HermesTimerProof' -Confirm:$false | Format-List } catch { $_.Exception.Message }
try{ Get-ScheduledTask -TaskName 'HermesTimerProof' | Format-List }catch{ $_.Exception.Message }
