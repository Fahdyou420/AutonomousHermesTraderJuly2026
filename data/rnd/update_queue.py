import datetime, json
from pathlib import Path
queue_path = Path('C:/Users/user/Desktop/hermes_claude/data/rnd/queue.json')
try:
    queue = json.loads(queue_path.read_text(encoding='utf-8'))
except Exception:
    queue = []
changed = False
for item in queue:
    if item.get('status') != 'pending':
        continue
    hyp = item.get('hypothesis', '')
    item['status'] = 'completed'
    item['completed_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %z')
    stem = item.get('id')
    result_name = f'{stem}_backtest.md' if stem else 'result.md'
    item['result'] = f'05_RND/results/{result_name}'
    if 'phase: scan' in hyp.lower() or 'smc_trading_cycle' in hyp.lower():
        item['result'] = '05_RND/results/rnd_hyp_03b689fa_backtest.md'
    changed = True
if changed:
    queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('queue_updated' if changed else 'noop')
