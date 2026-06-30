import os
import sys
import json
import glob
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Fix python paths for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Shared utilities
from services.shared.logger import get_logger
from services.preprocessor import indicators
from services.preprocessor import smc_detector

logger = get_logger("preprocessor")

app = FastAPI(title="Hermes Market Preprocessor Server", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_historical_and_live_bars(instrument: str, timeframe: str, n: int) -> List[Dict[str, Any]]:
    """
    Utility to load bars for a given symbol and tf.
    Searches:
    1. live_feed.jsonl (live active feed)
    2. Any {instrument}_{timeframe}_*.json historical/backtest file in market_data folder
    """
    collected_bars = []
    
    # 1. Search in saved backtest/historical files to get deep historical arrays
    search_dir = Path("/data/market_data")
    if search_dir.exists():
        # Match pattern: INSTRUMENT_TIMEFRAME_YYYYMMDD.json
        pattern = str(search_dir / f"{instrument.upper()}_{timeframe.upper()}_*.json")
        matched_files = sorted(glob.glob(pattern))
        
        # Read the latest matched history files first
        for file_path in reversed(matched_files):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_bars = json.load(f)
                    if isinstance(file_bars, list):
                        # Add them to collection
                        collected_bars.extend(file_bars)
                # If we already have more than double the required bars, we can optimize-stop
                if len(collected_bars) >= (n * 2):
                    break
            except Exception as e:
                logger.error(f"Error loading historical file {file_path}: {e}")

    # Ensure chronological ascending sort by timestamp before doing any live merges
    collected_bars = sorted(collected_bars, key=lambda x: int(x.get("timestamp", 0)))

    # 2. Add bars from live_feed.jsonl if they exist
    live_feed_path = search_dir / "live_feed.jsonl"
    live_bars = []
    if live_feed_path.exists():
        try:
            with open(live_feed_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        bar_dict = json.loads(line)
                        b_inst = bar_dict.get("instrument", "")
                        b_tf = bar_dict.get("timeframe", bar_dict.get("tf", ""))
                        if b_inst.upper() == instrument.upper() and b_tf.upper() == timeframe.upper():
                            live_bars.append(bar_dict)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error loading live feed bars: {e}")

    # Remove duplicates from live feed that might already exist in historical JSON files
    known_timestamps = {int(b.get("timestamp", 0)) for b in collected_bars}
    for lb in live_bars:
        ts = int(lb.get("timestamp", 0))
        if ts not in known_timestamps:
            collected_bars.append(lb)
            known_timestamps.add(ts)

    # Sort chronological ascending again to ensure perfect indexes
    final_bars = sorted(collected_bars, key=lambda x: int(x.get("timestamp", 0)))
    
    # Return last n bars
    return final_bars[-n:]


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/enriched")
async def get_enriched(
    instrument: str = "XAUUSD",
    tf: str = "M15",
    n: int = Query(default=500, ge=50, le=2000)
):
    """
    Collects raw bars and enriches them with ATR, EMAs, session categories,
    and Swing tags (is_swing_high / is_swing_low).
    """
    raw_bars = load_historical_and_live_bars(instrument, tf, n)
    if not raw_bars:
        return []

    # Enrich bars
    closes = [float(b.get("close", 0.0)) for b in raw_bars]
    ema20_arr = indicators.ema(closes, 20)
    ema50_arr = indicators.ema(closes, 50)
    atr14_arr = indicators.atr(raw_bars, 14)
    
    # Pre-fetch swings indices
    swing_highs_set = {s["index"] for s in indicators.swing_highs(raw_bars, lookback=5)}
    swing_lows_set = {s["index"] for s in indicators.swing_lows(raw_bars, lookback=5)}

    enriched_bars = []
    for idx, bar in enumerate(raw_bars):
        enriched = dict(bar)
        enriched["atr14"] = ema20_arr[idx] # fallback or direct indicator values
        enriched["ema20"] = ema20_arr[idx]
        enriched["ema50"] = ema50_arr[idx]
        
        # Calculate ATR and secure division limits
        atr_val = atr14_arr[idx]
        enriched["atr14"] = atr_val
        
        # Session identifier
        ts = int(bar.get("timestamp", 0))
        enriched["session"] = indicators.get_session(ts)
        
        # Spread ATR ratio tracking 
        spread = int(bar.get("spread", 0))
        if atr_val > 0:
            enriched["spread_atr_ratio"] = float(spread / (atr_val * 100))
        else:
            enriched["spread_atr_ratio"] = 0.0
            
        enriched["is_swing_high"] = (idx in swing_highs_set)
        enriched["is_swing_low"] = (idx in swing_lows_set)
        
        enriched_bars.append(enriched)
        
    return enriched_bars


@app.get("/smc_analysis")
async def get_smc_analysis(
    instrument: str = "XAUUSD",
    tf: str = "M15",
    n: int = Query(default=300, ge=50, le=1000)
):
    """
    Collects raw bars and runs structural sweeps returning:
    - Fair Value Gaps (FVG)
    - Order Blocks (OB)
    - Breaks of Structure (BOS)
    - Changes of Character (CHoCH)
    - Liquidity pools
    """
    raw_bars = load_historical_and_live_bars(instrument, tf, n)
    if not raw_bars:
        return {
            "fvg": [],
            "order_blocks": [],
            "bos": [],
            "choch": [],
            "liquidity": [],
            "swing_highs": [],
            "swing_lows": []
        }
        
    analysis = smc_detector.analyse_structure(raw_bars)
    return analysis


if __name__ == "__main__":
    port = int(os.getenv("PREPROCESSOR_PORT", "5559"))
    logger.info(f"Starting Hermes Preprocessor Service on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
