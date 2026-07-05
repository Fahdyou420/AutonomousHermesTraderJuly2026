import datetime
from pathlib import Path
path = Path('C:/Users/user/Desktop/hermes_claude/data/rnd/test_timer.log')
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %z')
with path.open('a', encoding='ascii') as f:
    f.write(ts + '\n')
    f.flush()
print('test_timer wrote', ts)
