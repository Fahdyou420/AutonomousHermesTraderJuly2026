"""Standalone backtest debug runner for BTCUSD M15 on host."""
import json, os, sys, glob
from pathlib import Path

# Make repo root importable
REPO = Path(r"C:/Users/user/Desktop/hermes_claude")
sys.path.insert(0, str(REPO))

from services.backtester.engine import BacktestEngine
from services.backtester.strategy_loader import load_strategy
from services.preprocessor.smc_detector import analyse_structure
from services.preprocessor.indicators import atr, ema, get_session
from services.shared.models import StrategyConfig

instrument = "BTCUSD"
timeframe = "M15"
search_dir = REPO / "data" / "market_data"
pattern = str(search_dir / f"{instrument.upper()}_{timeframe.upper()}_*.json")
matched = sorted(glob.glob(pattern))
print("matched_files", matched)

bars = []
for fp in matched:
    with open(fp, "r", encoding="utf-8") as f:
        bars.extend(json.load(f))
bars = sorted(bars, key=lambda x: int(x.get("timestamp", 0)))
print("raw_bars", len(bars))

# Enrich
closes = [float(b.get("close", 0.0)) for b in bars]
ema20_arr = ema(closes, 20)
ema50_arr = ema(closes, 50)
atr14_arr = atr(bars, 14)
for idx, bar in enumerate(bars):
    bar["atr14"] = atr14_arr[idx]
    bar["ema20"] = ema20_arr[idx]
    bar["ema50"] = ema50_arr[idx]
    bar["session"] = get_session(int(bar.get("timestamp", 0)))

# SMC
smc = analyse_structure(bars)
print("smc", {k: len(v) for k,v in smc.items()})

strategies = ["smc_ob_entry", "smc_fvg_fill", "smc_liquidity_sweep"]
for strat in strategies:
    cfg = StrategyConfig(
        strategy_id=f"debug_{strat}",
        name=f"Debug {strat}",
        instrument=instrument,
        timeframe=timeframe,
        session_filter=["london","newyork","overlap"],
        entry_logic={"type": strat, "description": ""},
        sl_logic={"type": "structure", "value": 15},
        tp_logic={"type": "fvg_fill", "value": 30},
        risk_pct=1.0,
        max_trades_per_day=2,
        spread_gate_pips=25,
        date_from="",
        date_to="",
    )
    engine = BacktestEngine(cfg)
    result = engine.run(bars)
    print(strat, "total_trades", result.total_trades, "win_rate", result.win_rate)
