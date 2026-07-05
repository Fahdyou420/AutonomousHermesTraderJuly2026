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
from services.shared.kill_switch import is_kill_switch_active, activate_kill_switch, deactivate_kill_switch

from services.execution.risk_gatekeeper import RiskGatekeeper
from services.execution.signal_generator import SignalGenerator
from services.execution.order_router import OrderRouter
from services.execution.chart_annotator import ChartAnnotator

logger = get_logger("execution")

app = FastAPI(title="Hermes Execution Engine", version="1.1")
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

    # 1. Check Kill-Switch
    if is_kill_switch_active():
        reason = "Trading halted due to active emergency kill switch."
        logger.warning(f"Signal {signal.signal_id} REJECTED: {reason}")
        signal.status = "rejected"
        payload = signal.to_dict()
        payload["status"] = "rejected"
        append_signal_log(REJECTED_LOG_FILE, payload, {"reason": reason})
        return {"status": "rejected", "reason": reason, "signal": payload}

    # 2. Check Idempotency via Redis key lock
    redis_key = f"hermes:processed_signals:{signal.signal_id}"
    try:
        # Check if already processed
        existing_status = redis_client.get(redis_key)
        if existing_status:
            logger.info(f"Signal {signal.signal_id} already has processed status: {existing_status}. Returning cached state.")
            return {
                "status": "duplicate",
                "reason": f"Signal {signal.signal_id} already processed (status: {existing_status})",
                "signal": signal.to_dict()
            }
        # Set temporary lock
        redis_client.set(redis_key, "processing", ex=300)
    except Exception as e:
        logger.error(f"Redis idempotency check failed: {e}")

    # 3. Check optional human approval required setting
    approval_required = os.getenv("APPROVAL_REQUIRED", "false").lower() == "true"
    if approval_required and signal.status != "approved_by_user":
        logger.info(f"Signal {signal.signal_id} held in queue awaiting manual approval.")
        signal.status = "pending_approval"
        payload = signal.to_dict()
        payload["status"] = "pending_approval"
        
        try:
            redis_client.set(f"hermes:pending_signals:{signal.signal_id}", json.dumps(payload), ex=86400)
            redis_client.publish("hermes:signals:pending", json.dumps(payload))
            redis_client.set(redis_key, "pending_approval", ex=86400)
        except Exception as e:
            logger.error(f"Failed to publish pending signal status: {e}")
            
        return {"status": "pending_approval", "reason": "User approval required", "signal": payload}

    # A. Account state
    paper_balance = float(os.getenv("PAPER_BALANCE", "10000.0"))
    account_state = {"balance": paper_balance, "equity": paper_balance, "daily_dd_pct": 0.0, "weekly_dd_pct": 0.0, "online": False}
    data = await _get("http://mt5_bridge:5558/account_state")
    if data:
        account_state.update(data)
        account_state["online"] = True
        # For paper mode, if the MT5 bridge returns balance=0.0 (demo/test environment with no funded account),
        # fall back to the configured PAPER_BALANCE so risk checks use a meaningful simulated balance.
        if mode != "live" and float(account_state.get("balance", 0.0)) <= 0.0:
            logger.warning(
                f"MT5 account_state reports balance=0.0. Falling back to PAPER_BALANCE={paper_balance} for paper risk calculations."
            )
            account_state["balance"] = paper_balance
            account_state["equity"] = paper_balance


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
            redis_client.set(redis_key, "approved", ex=86400)
            # Remove from pending queue if present
            redis_client.delete(f"hermes:pending_signals:{signal.signal_id}")
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
            redis_client.set(redis_key, "rejected", ex=86400)
            # Remove from pending queue if present
            redis_client.delete(f"hermes:pending_signals:{signal.signal_id}")
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
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "kill_switch_active": is_kill_switch_active()
    }


@app.post("/signal")
async def receive_signal_endpoint(data: Dict[str, Any]):
    try:
        signal = TradeSignal.from_dict(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid signal format: {e}")
    return await process_and_route_signal(signal)


# ─────────────────────────────────────────────────────────────────────────────
# NEW ENDPOINTS FOR KILL SWITCH AND HUMAN APPROVAL
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/kill")
async def trigger_emergency_kill(flatten: Optional[bool] = False):
    """Triggers the emergency kill switch and optionally flattens all open positions."""
    logger.critical("EMERGENCY KILL SWITCH TRIGGERED!")
    activate_kill_switch()
    
    response = {
        "status": "halted",
        "kill_switch_active": True,
        "positions_flattened": []
    }
    
    if flatten:
        # A. Flatten Paper Trader Positions
        try:
            paper_positions = await _get("http://paper_trader:5561/positions")
            if isinstance(paper_positions, list):
                for pos in paper_positions:
                    pos_id = pos.get("id")
                    if pos_id:
                        await _post(f"http://paper_trader:5561/close/{pos_id}", {})
                        response["positions_flattened"].append(f"paper_{pos_id}")
        except Exception as e:
            logger.error(f"Failed to flatten paper trades: {e}")
            
        # B. Flatten Live Positions
        try:
            live_positions = await _get("http://mt5_bridge:5558/positions")
            if isinstance(live_positions, list):
                for pos in live_positions:
                    ticket = pos.get("ticket")
                    symbol = pos.get("symbol")
                    if ticket and symbol:
                        # Call order router directly
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, lambda: order_router.send_close(ticket, symbol))
                        response["positions_flattened"].append(f"live_{ticket}")
        except Exception as e:
            logger.error(f"Failed to flatten live trades: {e}")
            
    return response


@app.post("/resume")
async def resume_trading_activity():
    """Deactivates the emergency kill switch and resumes trading."""
    logger.info("Resuming trading operations from emergency halt.")
    deactivate_kill_switch()
    return {"status": "active", "kill_switch_active": False}


@app.get("/pending_signals")
async def get_pending_signals_list():
    """Lists all signals awaiting manual user confirmation."""
    keys = []
    try:
        keys = redis_client.keys("hermes:pending_signals:*")
    except Exception:
        pass
    
    pending = []
    for k in keys:
        try:
            val = redis_client.get(k)
            if val:
                pending.append(json.loads(val))
        except Exception:
            pass
    return pending


@app.post("/signal/{signal_id}/approve")
async def approve_pending_signal(signal_id: str):
    """Confirm and execute a pending signal."""
    redis_key = f"hermes:pending_signals:{signal_id}"
    raw = redis_client.get(redis_key)
    if not raw:
        raise HTTPException(status_code=404, detail="Signal not found in pending confirmation queue.")
        
    data = json.loads(raw)
    data["status"] = "approved_by_user"
    signal = TradeSignal.from_dict(data)
    
    # Clean up locks to allow re-processing
    redis_client.delete(redis_key)
    redis_client.delete(f"hermes:processed_signals:{signal_id}")
    
    # Process signal again (will bypass approval check and execute)
    return await process_and_route_signal(signal)


@app.post("/signal/{signal_id}/reject")
async def reject_pending_signal(signal_id: str):
    """Discard a pending signal."""
    redis_key = f"hermes:pending_signals:{signal_id}"
    raw = redis_client.get(redis_key)
    if not raw:
        raise HTTPException(status_code=404, detail="Signal not found in pending confirmation queue.")
        
    data = json.loads(raw)
    data["status"] = "rejected_by_user"
    signal = TradeSignal.from_dict(data)
    
    logger.info(f"Signal {signal_id} rejected by user.")
    redis_client.delete(redis_key)
    redis_client.delete(f"hermes:processed_signals:{signal_id}")
    
    append_signal_log(REJECTED_LOG_FILE, signal.to_dict(), {"reason": "Rejected manually by user"})
    return {"status": "rejected", "signal_id": signal_id}


if __name__ == "__main__":
    port = int(os.getenv("EXECUTION_PORT", "5563"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
