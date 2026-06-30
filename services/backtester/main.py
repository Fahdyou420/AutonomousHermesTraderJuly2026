import os
import sys
import json
import glob
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Ensure correct python path for shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests

# Shared utilities
from services.shared.logger import get_logger
from services.shared.models import StrategyConfig, BacktestResult
from services.backtester.engine import BacktestEngine
from services.preprocessor.indicators import atr, ema, get_session

logger = get_logger("backtester")

app = FastAPI(title="Hermes Backtesting Service", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RESULTS_DIR = Path("/data/rnd/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

PREPROCESSOR_URL = os.getenv("PREPROCESSOR_URL", "http://preprocessor:5559")


def load_bars_from_preprocessor(instrument: str, timeframe: str) -> List[Dict[str, Any]]:
    """
    Attempts to fetch enriched bar series from the preprocessor microservice.
    Falls back to direct local file loads if the preprocessor port isn't reachable.
    """
    url = f"{PREPROCESSOR_URL}/enriched?instrument={instrument}&tf={timeframe}&n=1000"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"Could not reach preprocessor at {url}: {e}. Falling back to direct filesystem read.")

    # FALLBACK: Direct filesystem scanning
    collected_bars = []
    search_dir = Path("/data/market_data")
    if search_dir.exists():
        pattern = str(search_dir / f"{instrument.upper()}_{timeframe.upper()}_*.json")
        matched_files = sorted(glob.glob(pattern))
        for fp in matched_files:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    file_bars = json.load(f)
                    if isinstance(file_bars, list):
                        collected_bars.extend(file_bars)
            except Exception as fe:
                logger.error(f"Error loading local file {fp}: {fe}")

    # Chronological sort
    final_bars = sorted(collected_bars, key=lambda x: int(x.get("timestamp", 0)))
    if not final_bars:
        # Check live feed as desperate alternative
        live_feed = search_dir / "live_feed.jsonl"
        if live_feed.exists():
            try:
                with open(live_feed, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        bar_dict = json.loads(line)
                        if bar_dict.get("instrument", "").upper() == instrument.upper() and bar_dict.get("timeframe", "").upper() == timeframe.upper():
                            final_bars.append(bar_dict)
            except Exception as le:
                logger.error(f"Error reading live feed: {le}")

    # Re-sort
    final_bars = sorted(final_bars, key=lambda x: int(x.get("timestamp", 0)))

    # Local enrichment fallback
    if final_bars:
        closes = [float(b.get("close", 0.0)) for b in final_bars]
        ema20_arr = ema(closes, 20)
        ema50_arr = ema(closes, 50)
        atr14_arr = atr(final_bars, 14)
        for idx, bar in enumerate(final_bars):
            bar["atr14"] = atr14_arr[idx]
            bar["ema20"] = ema20_arr[idx]
            bar["ema50"] = ema50_arr[idx]
            bar["session"] = get_session(int(bar.get("timestamp", 0)))
            
    return final_bars


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.post("/backtest", response_model=BacktestResult)
async def run_backtest(config_data: StrategyConfig):
    """
    Receives StrategyConfig criteria, loads matching historical bars,
    processes bars through the backtest simulation, saves result to Disk, and returns.
    """
    logger.info(f"Incoming backtest request. Strategy: {config_data.strategy_id} | Symbol: {config_data.instrument} | Frame: {config_data.timeframe}")
    
    # Load bar histories
    bars = load_bars_from_preprocessor(config_data.instrument, config_data.timeframe)
    if not bars:
        raise HTTPException(status_code=404, detail=f"No matching bar data available for symbol {config_data.instrument} ({config_data.timeframe})")

    logger.info(f"Successfully loaded {len(bars)} bar(s) for simulate run.")

    # Initialize and execute simulator engine
    engine = BacktestEngine(config_data)
    result = engine.run(bars)

    # Save to disk
    out_path = RESULTS_DIR / f"{config_data.strategy_id}.json"
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.info(f"[✓] Saved backtest simulation records to: {out_path}")
    except Exception as e:
        logger.error(f"Failed to save simulation outcome to disk: {e}")

    return result


@app.get("/result/{strategy_id}")
async def get_result(strategy_id: str):
    """
    Retrieves previous backtest report for the strategy.
    """
    target_path = RESULTS_DIR / f"{strategy_id}.json"
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"No backtest results found for strategy: {strategy_id}")
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading result trace file: {str(e)}")


@app.get("/results")
async def list_results():
    """
    Lists metadata and index paths for all saved backtest simulation records.
    """
    reports = []
    for fp in RESULTS_DIR.glob("*.json"):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                rep = json.load(f)
                reports.append({
                    "strategy_id": rep.get("strategy_id", "UNKNOWN"),
                    "total_trades": rep.get("total_trades", 0),
                    "win_rate": rep.get("win_rate", 0.0),
                    "max_drawdown_pct": rep.get("max_drawdown_pct", 0.0),
                    "expectancy_r": rep.get("expectancy_r", 0.0),
                    "sharpe_ratio": rep.get("sharpe_ratio", 0.0),
                    "profit_factor": rep.get("profit_factor", 1.0),
                    "file_name": fp.name,
                    "created_at": datetime.fromtimestamp(fp.stat().st_mtime).isoformat() + "Z"
                })
        except Exception as e:
            logger.warning(f"Failed loading individual report {fp.name}: {e}")
            
    return reports


if __name__ == "__main__":
    port = int(os.getenv("BACKTESTER_PORT", "5560"))
    logger.info(f"Starting Hermes Backtester Service on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
