@echo off
schtasks.exe /Create /TN "HermesTimerProof" /TR "\"python.exe\" \"C:\Users\user\Desktop\hermes_claude\data\rnd\test_timer.py\"" /SC MINUTE /MO 2 /F
