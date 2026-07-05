@echo off
python.exe -c "import datetime; p=open('C:\Users\user\Desktop\hermes_claude\data\rnd\test_timer.log','a',encoding='ascii'); p.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %z')+'\n'); p.flush(); p.close()"
