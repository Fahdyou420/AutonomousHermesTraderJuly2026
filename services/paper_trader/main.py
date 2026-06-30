import os
import sys
import json
import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Ensure correct python path for shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import redis
import requests

# Shared utilities
from services.shared.logger import get_logger
from services.shared import redis_channels
from services.paper_trader.db import PaperTradeDB

logger = get_logger("paper_trader")

app = FastAPI(title="Hermes Paper Trader Service", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MT5_BRIDGE_URL = os.getenv("MT5_BRIDGE_URL", "http://mt5_bridge:5558")

# Redis configuration block
logger.info(f"Connecting paper trader to Redis at {REDIS_URL}...")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Database instance
db = PaperTradeDB()

class TradeSignalInput(BaseModel):
    signal_id: Optional[str] = None
    timestamp: Optional[int] = None
    instrument: str
    direction: str
    entry_price: float
    entry_type: Optional[str] = "market"
    sl: float
    tp: float
    lots: float
    timeframe: str
    strategy_id: str
    setup_type: str
    session: str
    mode: Optional[str] = "paper"
    r_ratio: Optional[float] = 0.0
    confidence: Optional[str] = "medium"
    agent_notes: Optional[str] = ""
    status: Optional[str] = "pending"

def model_to_dict(m: BaseModel) -> Dict[str, Any]:
    if hasattr(m, "model_dump"):
        return m.model_dump()
    return m.dict()


async def check_active_positions():
    """
    Checks if active positions have hit SL/TP targets using latest bars from mt5_bridge.
    """
    open_positions = db.get_open_positions()
    if not open_positions:
        return
        
    for pos in open_positions:
        instrument = pos["instrument"]
        pos_id = pos["id"]
        
        try:
            # Query mt5_bridge for latest price bar
            url = f"{MT5_BRIDGE_URL}/latest_bars?instrument={instrument}&tf=M15&n=1"
            resp = await asyncio.get_event_loop().run_in_executor(
                None, lambda: requests.get(url, timeout=5)
            )
            if resp.status_code != 200:
                continue
                
            bars = resp.json()
            if not bars:
                continue
                
            latest_bar = bars[-1]
            high = float(latest_bar.get("high", 0.0))
            low = float(latest_bar.get("low", 0.0))
            close = float(latest_bar.get("close", 0.0))
            
            sl = float(pos["sl"])
            tp = float(pos["tp"])
            direction = pos["direction"].lower()
            
            # Check exit criteria
            hit_sl = False
            hit_tp = False
            exit_price = 0.0
            reason = ""
            
            if direction in ["long", "buy"]:
                # If both SL and TP are hit inside the same candle, trigger SL (conservative baseline)
                if low <= sl and high >= tp:
                    hit_sl = True
                    exit_price = sl
                    reason = "sl"
                elif low <= sl:
                    hit_sl = True
                    exit_price = sl
                    reason = "sl"
                elif high >= tp:
                    hit_tp = True
                    exit_price = tp
                    reason = "tp"
            else: # short/sell
                if high >= sl and low <= tp:
                    hit_sl = True
                    exit_price = sl
                    reason = "sl"
                elif high >= sl:
                    hit_sl = True
                    exit_price = sl
                    reason = "sl"
                elif low <= tp:
                    hit_tp = True
                    exit_price = tp
                    reason = "tp"
                    
            if hit_sl or hit_tp:
                close_time = int(latest_bar.get("timestamp", time.time() if "time" not in globals() else 0)) or int(datetime.utcnow().timestamp())
                logger.info(f"[!] Trigger check hit. Closing Position: {pos_id} ({instrument}) at {exit_price}. Reason: {reason}")
                db.close_position(pos_id, exit_price, reason, close_time=close_time)
                
                # Fetch closed record to publish event update
                with db._get_conn() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM positions WHERE id = ?", (pos_id,))
                    updated_row = cur.fetchone()
                    
                if updated_row:
                    updated_dict = dict(updated_row)
                    # Publish event to REDIS
                    redis_client.publish(redis_channels.PAPER_TRADE_UPDATE, json.dumps(updated_dict))
                    
        except Exception as e:
            logger.error(f"Error checking targets for position {pos_id}: {e}")


async def paper_trader_background_loop():
    """
    Background worker loop firing every 30 seconds to parse and liquidate positions hitting SL/TP boundaries.
    """
    while True:
        try:
            await check_active_positions()
        except Exception as ex:
            logger.error(f"Unhandled error in paper trader positions checks: {ex}")
        await asyncio.sleep(30)


@app.on_event("startup")
async def startup_event():
    """Kicks off the core background monitor tasks."""
    logger.info("Initializing Hermes Paper Trader loops...")
    asyncio.create_task(paper_trader_background_loop())


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.post("/signal")
async def receive_signal(signal: TradeSignalInput):
    """
    Ingests TradeSignal events, pushes into the tracking DB, and publishes trade details.
    """
    logger.info(f"Broker received signal: Instrument {signal.instrument}, Side {signal.direction}, Lots {signal.lots}")
    
    # Write into SQLite
    payload = model_to_dict(signal)
    pos_id = db.open_position(payload)
    
    # Retrieve details inside dictionary structure
    with db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM positions WHERE id = ?", (pos_id,))
        row = cur.fetchone()
        
    pos_dict = {}
    if row:
        pos_dict = dict(row)
        try:
            # Publish TRADE_OPENED event to Redis
            redis_client.publish(redis_channels.TRADE_OPENED, json.dumps(pos_dict))
            logger.info(f"[✓] Published TRADE_OPENED to Redis for signal ID: {pos_id}")
        except Exception as re:
            logger.error(f"Redis publish failure on TRADE_OPENED channel: {re}")
            
    return {"status": "opened", "position_id": pos_id, "data": pos_dict}


@app.get("/positions")
async def get_active_positions():
    """Returns currently open paper trade positions."""
    return db.get_open_positions()


@app.get("/history")
async def get_closed_history(n: int = Query(default=100, ge=1, le=1000)):
    """Returns historical closed paper trade records."""
    return db.get_history(n)


@app.get("/stats")
async def get_running_stats():
    """Returns overall running performance indices."""
    return db.get_stats()


@app.post("/close/{trade_id}")
async def manual_close_position(trade_id: str):
    """
    Closes a position manually at the current close price.
    """
    # Fetch details first
    with db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM positions WHERE id = ? AND status = 'open'", (trade_id,))
        row = cur.fetchone()
        
    if not row:
        raise HTTPException(status_code=404, detail=f"No active open position found matching id: {trade_id}")
        
    pos = dict(row)
    instrument = pos["instrument"]
    close_price = float(pos["entry_price"]) # default fallback
    
    # Gather ticks
    try:
        url = f"{MT5_BRIDGE_URL}/latest_bars?instrument={instrument}&tf=M15&n=1"
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: requests.get(url, timeout=5))
        if resp.status_code == 200:
            bars = resp.json()
            if bars:
                close_price = float(bars[-1].get("close", close_price))
    except Exception as e:
        logger.warning(f"Could not reach bridge to read close price for {instrument}: {e}. Closing at entry fallback.")

    # Commit Close
    db.close_position(trade_id, close_price, reason="manual")
    
    # Retrieve updated row
    with db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM positions WHERE id = ?", (trade_id,))
        updated_row = cur.fetchone()
        
    updated_dict = {}
    if updated_row:
        updated_dict = dict(updated_row)
        try:
            # Publish PAPER_TRADE_UPDATE to signify status changes
            redis_client.publish(redis_channels.PAPER_TRADE_UPDATE, json.dumps(updated_dict))
        except Exception as re:
            logger.error(f"Failed to publish manual close event to Redis: {re}")
            
    return {"status": "closed", "trade_id": trade_id, "close_price": close_price, "data": updated_dict}


@app.get("/promotion_candidates")
async def get_promotion_candidates():
    """
    Retrieves strategy-level groupings and filters them with candidates criteria:
    win_rate >= 0.52 AND expectancy_r >= 0.5 AND max_dd_pct <= 8.0 AND total_trades >= 30
    """
    strategy_groups = db.get_strategy_performance()
    candidates = []
    
    for sg in strategy_groups:
        wr = sg.get("win_rate", 0.0)
        # Normalize in case win_rate is percentage (e.g. 52.0 vs 0.52)
        norm_wr = wr if wr <= 1.0 else (wr / 100.0)
        
        expectancy = sg.get("expectancy_r", 0.0)
        max_dd = sg.get("max_dd_pct", 0.0)
        total_trades = sg.get("total_trades", 0)
        
        if norm_wr >= 0.52 and expectancy >= 0.5 and max_dd <= 8.0 and total_trades >= 30:
            candidates.append(sg)
            
    return candidates


if __name__ == "__main__":
    port = int(os.getenv("PAPER_TRADER_PORT", "5561"))
    logger.info(f"Starting Hermes Paper Trader microservice on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
