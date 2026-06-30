import os
import sys
import json
import asyncio
import requests
import redis
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from services.shared.logger import get_logger
from services.shared import redis_channels
from services.shared.models import TradeSignal
from services.shared.error_bus import publish_error

from services.execution.risk_gatekeeper import RiskGatekeeper
from services.execution.signal_generator import SignalGenerator
from services.execution.order_router import OrderRouter
from services.execution.chart_annotator import ChartAnnotator

logger = get_logger("execution")

app = FastAPI(title="Hermes Execution Engine", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

risk_gatekeeper = RiskGatekeeper()
order_router = OrderRouter()
chart_annotator = ChartAnnotator()

LOGS_DIR = Path("/data/trades")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
APPROVED_LOG_FILE = LOGS_DIR / "approved_signals.jsonl"
REJECTED_LOG_FILE = LOGS_DIR / "rejected_signals.jsonl"


def append_signal_log(file_path: Path, payload: dict, extra: Optional[dict] = None):
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": int(datetime.utcnow().timestamp()),
                "signal": payload,
                "extra": extra or {}
            }) + "\n")
    except Exception as e:
        logger.error(f"Failed to write signal log {file_path}: {e}")


async def _get(url: str, timeout: int = 3) -> Optional[Any]:
    """Non-blocking GET using run_in_executor."""
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(None, lambda: requests.get(url, timeout=timeout))
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"GET {url} failed: {e}")
    return None


async def _post(url: str, payload: dict, timeout: int = 5) -> Optional[Any]:
    """Non-blocking POST using run_in_executor."""
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(
            None, lambda: requests.post(url, json=payload,
                                        headers={"Content-Type": "application/json"},
                                        timeout=timeout)
        )
        if resp.status_code in [200, 201]:
            return resp.json()
        logger.warning(f"POST {url} returned {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.warning(f"POST {url} failed: {e}")
    return None


async def process_and_route_signal(signal: TradeSignal) -> dict:
    mode = str(signal.mode or "paper").lower()
    instrument = signal.instrument
    logger.info(f"Processing signal {signal.signal_id} ({instrument} {signal.direction}) mode={mode}")

    # A. Account state
    account_state = {"balance": 10000.0, "equity": 10000.0, "daily_dd_pct": 0.0, "weekly_dd_pct": 0.0}
    data = await _get("http://mt5_bridge:5558/account_state")
    if data:
        account_state.update(data)

    # B. Open positions
    open_positions = []
    if mode == "live":
        data = await _get("http://mt5_bridge:5558/positions")
    else:
        data = await _get("http://paper_trader:5561/positions")
    if data and isinstance(data, list):
        open_positions = data

    # C. Calendar
    calendar_events = []
    data = await _get("http://mt5_bridge:5558/calendar", timeout=2)
    if data and isinstance(data, list):
        calendar_events = data

    # D. Risk gate
    is_approved, reason = risk_gatekeeper.check(signal, account_state, open_positions, calendar_events)
    payload = signal.to_dict()

    if is_approved:
        signal.status = "approved"
        payload["status"] = "approved"
        logger.info(f"Signal APPROVED: {signal.signal_id}")

        try:
            chart_annotator.draw_trade(signal)
        except Exception as e:
            logger.error(f"Chart annotator error: {e}")

        route_status = "routed"
        route_detail = ""

        if mode == "live":
            routed_ok = order_router.send_order(signal)
            if not routed_ok:
                route_status = "error_dispatch"
                route_detail = "ZMQ dispatch failed"
                publish_error("execution", "ERROR", "Live order dispatch failed", signal.signal_id)
        else:
            result = await _post("http://paper_trader:5561/signal", payload)
            if result:
                route_detail = result.get("position_id", "")
            else:
                route_status = "error_paper"
                route_detail = "Paper trader unreachable"
                publish_error("execution", "ERROR", "Paper trader signal failed", signal.signal_id)

        try:
            redis_client.publish(redis_channels.SIGNAL_APPROVED, json.dumps({
                "signal": payload, "route_status": route_status,
                "route_detail": route_detail, "approved_at": datetime.utcnow().isoformat() + "Z"
            }))
        except Exception as e:
            logger.error(f"Redis publish APPROVED failed: {e}")

        append_signal_log(APPROVED_LOG_FILE, payload, {"route_status": route_status, "route_detail": route_detail})
        return {"status": "approved", "reason": reason, "route_status": route_status,
                "route_detail": route_detail, "signal": payload}

    else:
        signal.status = "rejected"
        payload["status"] = "rejected"
        logger.warning(f"Signal REJECTED: {reason}")

        try:
            redis_client.publish(redis_channels.SIGNAL_REJECTED, json.dumps({
                "signal": payload, "reason": reason,
                "rejected_at": datetime.utcnow().isoformat() + "Z"
            }))
        except Exception as e:
            logger.error(f"Redis publish REJECTED failed: {e}")

        append_signal_log(REJECTED_LOG_FILE, payload, {"reason": reason})
        return {"status": "rejected", "reason": reason, "signal": payload}


async def redis_listener_loop():
    logger.info("Starting Redis AGENT_MESSAGE listener...")
    pubsub = redis_client.pubsub()
    try:
        pubsub.subscribe(redis_channels.AGENT_MESSAGE)
    except Exception as e:
        logger.critical(f"Redis subscription failed: {e}")
        return

    while True:
        try:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                msg_body = message.get("data", "")
                if msg_body:
                    signal = SignalGenerator.parse_agent_output(str(msg_body))
                    if signal:
                        asyncio.create_task(process_and_route_signal(signal))
            await asyncio.sleep(0.1)
        except Exception as ex:
            logger.error(f"Listener loop error: {ex}")
            publish_error("execution", "ERROR", "Redis listener crashed", str(ex))
            await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_listener_loop())


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.post("/signal")
async def receive_signal_endpoint(data: Dict[str, Any]):
    try:
        signal = TradeSignal.from_dict(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid signal format: {e}")
    return await process_and_route_signal(signal)


if __name__ == "__main__":
    port = int(os.getenv("EXECUTION_PORT", "5563"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
