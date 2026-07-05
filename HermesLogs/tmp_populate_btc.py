
import os, json
from pathlib import Path
import yfinance as yf

base = Path(r"C:/Users/user/Desktop/hermes_claude/data/market_data")
base.mkdir(parents=True, exist_ok=True)

instrument = "BTCUSD"
ticker = "BTC-USD"
timeframes = {
    "M15": {"interval": "15m", "period": "60d"},
    "H1": {"interval": "60m", "period": "1y"},
    "H4": {"interval": "1h", "period": "2y"},
    "D1": {"interval": "1d", "period": "5y"},
}

written = {}

def _safe_vol(v):
    try:
        x = float(v)
        return 0.0 if x != x else x
    except Exception:
        return 0.0

for tf, cfg in timeframes.items():
    df = yf.download(ticker, period=cfg["period"], interval=cfg["interval"], progress=False, auto_adjust=True)
    if df.empty:
        written[tf] = f"empty:{cfg['interval']}"
        continue
    cols = ["Open","High","Low","Close","Volume"]
    if not all(c in df.columns for c in ["Open","High","Low","Close"]):
        written[tf] = "missing_ohlc"
        continue
    out = []
    for ts, row in df.iterrows():
        def _scalar(v):
            try:
                return float(v)
            except Exception:
                return float(v.iloc[0])
        out.append({
            "instrument": instrument,
            "timeframe": tf,
            "timestamp": int(ts.timestamp()),
            "open": _scalar(row["Open"]),
            "high": _scalar(row["High"]),
            "low": _scalar(row["Low"]),
            "close": _scalar(row["Close"]),
            "volume": int(_safe_vol(row.get("Volume", 0))),
            "spread": 0,
        })
    fp = base / f"{instrument}_{tf}_yfinance.json"
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f)
    written[tf] = f"bars={len(out)} file={fp.name}"

canvas = json.dumps(written)
print(canvas)
