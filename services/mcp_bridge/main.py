import os
import sys
import json
import asyncio
import httpx
import redis
import requests
import zmq
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.shared.logger import get_logger
from services.shared import redis_channels
from services.shared.error_bus import publish_error

logger = get_logger("mcp_bridge")

app = FastAPI(title="Hermes MCP Bridge", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
HOST_RPC_URL = os.getenv("HOST_RPC_URL", "http://host.docker.internal:7778")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)
chunk_counter = 0

# ZMQ draw socket
try:
    zmq_ctx = zmq.Context()
    zmq_draw_socket = zmq_ctx.socket(zmq.PUSH)
    zmq_draw_socket.setsockopt(zmq.LINGER, 1000)
    zmq_draw_socket.setsockopt(zmq.SNDTIMEO, 2000)
    zmq_draw_uri = os.getenv("DRAW_ZMQ_URI", "tcp://host.docker.internal:5556")
    zmq_draw_socket.connect(zmq_draw_uri)
    logger.info(f"ZMQ draw socket connected to {zmq_draw_uri}")
except Exception as ze:
    logger.error(f"ZMQ init failed: {ze}")
    zmq_draw_socket = None


class ToolRequest(BaseModel):
    tool_name: str
    params: Dict[str, Any]


@app.post("/signal")
async def signal_proxy_endpoint(data: Dict[str, Any]):
    """Proxy trade signal to execution engine."""
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(
            None, lambda: requests.post("http://execution:5563/signal", json=data, timeout=10)
        )
        return resp.json()
    except Exception as e:
        publish_error("mcp_bridge", "ERROR", "Signal proxy to execution failed", str(e))
        raise HTTPException(status_code=500, detail=f"Execution engine unreachable: {e}")


@app.post("/draw")
async def draw_proxy_endpoint(data: Dict[str, Any]):
    """Publish draw command to Redis CHART_DRAW_CMD channel."""
    try:
        redis_client.publish(redis_channels.CHART_DRAW_CMD, json.dumps(data))
        return {"success": True}
    except Exception as e:
        publish_error("mcp_bridge", "ERROR", "Draw command publish failed", str(e))
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")


@app.post("/tool")
async def tool_proxy_endpoint(payload: ToolRequest):
    """Proxy tool call to hermes_rpc on Windows host."""
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(
            None, lambda: requests.post(
                f"{HOST_RPC_URL}/tool",
                json={"tool_name": payload.tool_name, "params": payload.params},
                timeout=120
            )
        )
        if resp.status_code != 200:
            logger.error(f"Host RPC /tool returned {resp.status_code}: {resp.text}")
            return {"success": False, "error": f"Host returned {resp.status_code}", "result": None}
        return resp.json()
    except Exception as e:
        publish_error("mcp_bridge", "ERROR", f"Tool proxy failed: {payload.tool_name}", str(e))
        return {"success": False, "error": str(e), "result": None}


@app.get("/health")
async def health():
    """Health check - verify hermes_rpc reachability."""
    loop = asyncio.get_event_loop()
    rpc_ok = False
    try:
        resp = await loop.run_in_executor(
            None, lambda: requests.get(f"{HOST_RPC_URL}/health", timeout=2)
        )
        rpc_ok = resp.status_code == 200
    except Exception:
        pass

    return {
        "status": "ok" if rpc_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "host_rpc": "online" if rpc_ok else "offline",
        "redis": "connected"
    }


async def send_async_chat_request(chat_payload: dict):
    """Fire-and-forget chat to hermes_rpc for post-backtest analysis."""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", f"{HOST_RPC_URL}/chat", json=chat_payload) as r:
                if r.status_code != 200:
                    logger.error(f"Background chat failed: {r.status_code}")
                    return
                async for _ in r.aiter_lines():
                    pass  # consume stream
    except Exception as e:
        logger.error(f"Background chat exception: {e}")


async def redis_subscription_handler():
    """Subscribe to Redis channels: BACKTEST_COMPLETE, NEW_DOCUMENT_CHUNK, CHART_DRAW_CMD."""
    global chunk_counter
    pubsub = redis_client.pubsub()
    try:
        pubsub.subscribe(
            redis_channels.BACKTEST_COMPLETE,
            redis_channels.NEW_DOCUMENT_CHUNK,
            redis_channels.CHART_DRAW_CMD
        )
        logger.info("MCP Bridge Redis subscriptions active.")
    except Exception as e:
        logger.critical(f"Redis PubSub failed: {e}")
        return

    while True:
        try:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                channel = message.get("channel")
                data_raw = message.get("data", "")

                if channel == redis_channels.BACKTEST_COMPLETE:
                    try:
                        payload = json.loads(data_raw)
                        strategy_id = payload.get("strategy_id", "unknown")
                        summary = payload.get("summary", payload.get("results", str(payload)))
                        asyncio.create_task(send_async_chat_request({
                            "message": f"Backtest complete for {strategy_id}. Results: {summary}. Analyse and update vault strategy card.",
                            "task_type": "analysis"
                        }))
                    except Exception as e:
                        logger.error(f"BACKTEST_COMPLETE parse error: {e}")

                elif channel == redis_channels.NEW_DOCUMENT_CHUNK:
                    chunk_counter += 1
                    if chunk_counter % 100 == 0:
                        logger.info(f"Document chunk #{chunk_counter} received.")

                elif channel == redis_channels.CHART_DRAW_CMD:
                    if zmq_draw_socket:
                        try:
                            zmq_draw_socket.send_string(data_raw)
                        except Exception as e:
                            logger.error(f"ZMQ draw forward failed: {e}")
                            publish_error("mcp_bridge", "ERROR", "ZMQ draw forward failed", str(e))

            await asyncio.sleep(0.05)
        except Exception as ex:
            logger.error(f"PubSub loop error: {ex}")
            await asyncio.sleep(5.0)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_subscription_handler())


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MCP_BRIDGE_PORT", "5562"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
