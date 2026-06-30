import os
import re
import sys
import json
import logging
import requests
import httpx
from datetime import datetime, date
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (HermesRPC) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("hermes_rpc")

app = FastAPI(title="Hermes Host RPC Server", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration defaults for Windows Host execution environment
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
VAULT_ROOT  = os.getenv("OBSIDIAN_VAULT_ROOT", "C:\\Fahd data AI\\Fahd\\Vault")

# Discover the actual model names installed in Ollama at startup
# rather than hardcoding names that may not match
def _discover_ollama_model(preference_keywords: list, fallback: str) -> str:
    """Return the first installed Ollama model whose name contains any preference keyword."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            if not models:
                return fallback
            # Try preference keywords in order
            for kw in preference_keywords:
                for m in models:
                    if kw.lower() in m.lower():
                        return m
            # Nothing matched — return first available model
            return models[0]
    except Exception:
        pass
    return fallback

# Resolved at import time — picks the right model name whatever Ollama has installed
_ANALYSIS_MODEL = os.getenv("MODEL_ANALYSIS") or _discover_ollama_model(
    ["hermes", "llama3", "mistral", "qwen"], "llama3.2")
_CODE_MODEL     = os.getenv("MODEL_CODE")     or _discover_ollama_model(
    ["qwen2.5-coder", "qwen", "codellama", "deepseek-coder"], _ANALYSIS_MODEL)
_BULK_MODEL     = os.getenv("MODEL_BULK")     or _discover_ollama_model(
    ["llama3.2:3b", "llama3.2", "phi3", "gemma"], _ANALYSIS_MODEL)

logging.getLogger(__name__).info(
    f"Ollama models resolved — analysis:{_ANALYSIS_MODEL} code:{_CODE_MODEL} bulk:{_BULK_MODEL}")

# Task -> Ollama model selection mappings
MODEL_MAP = {
    "analysis":    _ANALYSIS_MODEL,
    "research":    _ANALYSIS_MODEL,
    "execution":   _ANALYSIS_MODEL,
    "monitoring":  _ANALYSIS_MODEL,
    "review":      _ANALYSIS_MODEL,
    "initialization": _ANALYSIS_MODEL,
    "code":        _CODE_MODEL,
    "bulk":        _BULK_MODEL,
}

class ChatPayload(BaseModel):
    message: str
    task_type: Optional[str] = "analysis"
    context: Optional[Dict[str, Any]] = None

class ToolExecutionPayload(BaseModel):
    tool_name: str
    params: Dict[str, Any]


def load_system_prompt() -> str:
    """
    Surgically scans for AGENTS.md profile configurations to construct the AI persona.
    """
    search_paths = [
        os.path.join(".", "hermes_config", "AGENTS.md"),
        os.path.join(".", "AGENTS.md"),
        os.path.join("..", "hermes_config", "AGENTS.md"),
        os.path.join("..", "AGENTS.md"),
        os.path.join(VAULT_ROOT, "AGENTS.md")
    ]
    
    for p in search_paths:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    logger.info(f"Loaded active system persona file from: {p}")
                    return f.read()
        except Exception as e:
            logger.debug(f"Path skipped: {p} ({e})")
            
    # Premium production default if instructions missing on local machine paths
    logger.warning("AGENTS.md system instructions unreached. Binding standard persona baseline...")
    return (
        "You are 'Hermes Trading Agent', a state-of-the-art self-improving autonomous AI system.\n"
        "You trade XAUUSD using institutional Smart Money Concepts (SMC) & Inner Circle Trader (ICT) concepts.\n"
        "Your responses should remain highly precise, logical, and evidence-driven.\n"
    )

# ==========================================
# TOOL REGISTRY IMPLEMENTATIONS
# ==========================================

def read_market_bars(instrument: str, tf: str = "M15", n: int = 100) -> List[Dict[str, Any]]:
    """Retrieves standard OHLCV prices from locally mapped MT5 bridge container."""
    url = f"http://localhost:5558/latest_bars?instrument={instrument}&tf={tf}&n={n}"
    logger.info(f"Retrieving {n} candles for {instrument} ({tf}) from {url}...")
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Market bars endpoint error: {resp.status_code} {resp.text}")
        return []
    except Exception as e:
        logger.error(f"Failed carrying read_market_bars: {e}")
        return []


def write_obsidian_note(path: str, content: str, frontmatter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Writes markdown note structure into user's designated Obsidian Vault safely."""
    logger.info(f"Writing note to path: {path}")
    try:
        full_path = os.path.normpath(os.path.join(VAULT_ROOT, path))
        
        # Guard against traversal out of the workspace filesystem root
        if not full_path.lower().startswith(os.path.normpath(VAULT_ROOT).lower()):
            return {"success": False, "error": "Traversal breach detected: Target path must remain inside designated Obsidian root."}
            
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Build YAML block
        fm_str = ""
        if frontmatter:
            fm_str = "---\n"
            for k, v in frontmatter.items():
                # Format dates or dicts cleanly
                if isinstance(v, (dict, list)):
                    fm_str += f"{k}: {json.dumps(v)}\n"
                else:
                    fm_str += f"{k}: {v}\n"
            fm_str += "---\n\n"
            
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(fm_str + content)
            
        return {"success": True, "path": path, "size_bytes": len(content)}
    except Exception as e:
        logger.error(f"Failed executing write_obsidian_note: {e}")
        return {"success": False, "error": str(e)}


def read_obsidian_note(path: str) -> Dict[str, Any]:
    """Reads target markdown note from designated Obsidian Vault."""
    logger.info(f"Reading note from path: {path}")
    try:
        full_path = os.path.normpath(os.path.join(VAULT_ROOT, path))
        if not full_path.lower().startswith(os.path.normpath(VAULT_ROOT).lower()):
            return {"success": False, "error": "Traversal breach detected: Target path must remain inside designated Obsidian root."}
            
        if not os.path.exists(full_path):
            return {"success": False, "error": f"File does not exist under vault: {path}"}
            
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return {"success": True, "path": path, "content": content}
    except Exception as e:
        logger.error(f"Failed performing read_obsidian_note: {e}")
        return {"success": False, "error": str(e)}


def search_vault(query: str) -> List[Dict[str, Any]]:
    """Performs full-text case-insensitive query scans across all documents in vault."""
    logger.info(f"Performing vault keyword search: '{query}'")
    results = []
    q_lower = query.lower()
    
    try:
        if not os.path.exists(VAULT_ROOT):
            logger.warning(f"Vault folder {VAULT_ROOT} does not exist.")
            return []
            
        for root, _, files in os.walk(VAULT_ROOT):
            for file in files:
                if file.endswith(".md"):
                    f_path = os.path.join(root, file)
                    try:
                        with open(f_path, "r", encoding="utf-8") as f:
                            text = f.read()
                            if q_lower in text.lower():
                                pos = text.lower().find(q_lower)
                                start = max(0, pos - 100)
                                end = min(len(text), pos + len(query) + 150)
                                snippet = text[start:end].replace("\n", " ").strip()
                                results.append({
                                    "path": os.path.relpath(f_path, VAULT_ROOT),
                                    "excerpt": f"...{snippet}..."
                                })
                    except Exception:
                        pass # bypass unreadable files
                        
        return results
    except Exception as e:
        logger.error(f"Failed searching vault: {e}")
        return []


def query_knowledge_base(query: str, collection: str, n_results: int = 5) -> Dict[str, Any]:
    """Queries persistent Chroma DB vector nodes without binary bindings using requests."""
    logger.info(f"Querying KB vector collection '{collection}' for: '{query}'")
    try:
        # First query standard collections catalog to extract unique ID
        cat_url = "http://localhost:8000/api/v1/collections"
        cat_resp = requests.get(cat_url, timeout=5)
        if cat_resp.status_code != 200:
            return {"success": False, "error": f"Chroma returned status: {cat_resp.status_code}"}
            
        collections = cat_resp.json()
        target_id = None
        for col in collections:
            if col.get("name") == collection:
                target_id = col.get("id")
                break
                
        if not target_id:
            return {"success": False, "error": f"No vector library matches name: {collection}"}
            
        # Dispatch vectorized distance search
        query_url = f"http://localhost:8000/api/v1/collections/{target_id}/query"
        payload = {
            "query_embeddings": None,
            "n_results": int(n_results),
            "where": {},
            "where_document": {},
            "query_texts": [query]
        }
        resp = requests.post(query_url, json=payload, timeout=10)
        if resp.status_code == 200:
            return {"success": True, "results": resp.json()}
        return {"success": False, "error": f"Chroma Query failed: {resp.status_code} {resp.text}"}
    except Exception as e:
        logger.error(f"Chroma connection failed: {e}")
        return {"success": False, "error": f"Vector network unreachable: {e}"}


def run_backtest(strategy_config: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatches programmatic SMC strategy configuration backtest onto simulator container."""
    url = "http://localhost:5560/backtest"
    logger.info(f"Dispatching strategy run against backtester socket at {url}...")
    try:
        resp = requests.post(url, json=strategy_config, timeout=180)
        if resp.status_code == 200:
            return {"success": True, "results": resp.json()}
        return {"success": False, "error": f"Backtest engine returned: {resp.status_code} {resp.text}"}
    except Exception as e:
        logger.error(f"Backtest execution failed: {e}")
        return {"success": False, "error": str(e)}


def get_paper_trade_status() -> Dict[str, Any]:
    """Retrieves operational diagnostics/balances and open positions index from internal paper tracer."""
    logger.info("Reading active Paper trading states...")
    stats = {}
    positions = []
    
    try:
        s_resp = requests.get("http://localhost:5561/stats", timeout=5)
        if s_resp.status_code == 200:
            stats = s_resp.json()
    except Exception as e:
        stats = {"error": f"Unreachable: {e}"}
        
    try:
        p_resp = requests.get("http://localhost:5561/positions", timeout=5)
        if p_resp.status_code == 200:
            positions = p_resp.json()
    except Exception as e:
        positions = {"error": f"Unreachable: {e}"}
        
    return {
        "success": True,
        "metrics_summary": stats,
        "positions_active": positions
    }


def send_trade_signal(signal_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Pushes generated trade ideas to mcp_bridge for risk qualification and execution."""
    url = "http://localhost:5562/signal"
    logger.info(f"Forwarding trade signal execution schema to broker gateway: {url}")
    try:
        resp = requests.post(url, json=signal_dict, timeout=10)
        if resp.status_code == 200:
            return {"success": True, "result": resp.json()}
        return {"success": False, "error": f"Signal Router rejected: {resp.status_code} {resp.text}"}
    except Exception as e:
        logger.error(f"Broker connection drop: {e}")
        return {"success": False, "error": str(e)}


def draw_on_chart(draw_command_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Routes annotation vectors to chart canvas displays."""
    url = "http://localhost:5562/draw"
    logger.info(f"Dispatched draw request to active rendering panel: {url}")
    try:
        resp = requests.post(url, json=draw_command_dict, timeout=10)
        if resp.status_code == 200:
            return {"success": True, "result": resp.json()}
        return {"success": False, "error": f"Renderer returned code: {resp.status_code} {resp.text}"}
    except Exception as e:
        logger.error(f"Renderer communication drop: {e}")
        return {"success": False, "error": str(e)}


def get_economic_calendar() -> List[Dict[str, Any]]:
    """
    Retrieves macroeconomics calendar data via Forex Factory XML API feed.
    Surgically isolates High impact entries specifically.
    """
    feed_url = "https://www.forexfactory.com/ff_calendar_thisweek.xml"
    logger.info(f"Scraping macroeconomic calendars from official XML source: {feed_url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    events = []
    
    try:
        resp = requests.get(feed_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.error(f"ForexFactory calendar retrieval error: {resp.status_code}")
            return []
            
        root = ET.fromstring(resp.content)
        today_date = date.today().strftime("%m-%d-%Y") # formats such as "06-08-2026"
        
        for event in root.findall("event"):
            imp = event.find("impact").text if event.find("impact") is not None else ""
            # Capture only HIGH impact indexes
            if imp.lower() == "high":
                title = event.find("title").text if event.find("title") is not None else ""
                country = event.find("country").text if event.find("country") is not None else ""
                event_date = event.find("date").text if event.find("date") is not None else ""
                event_time = event.find("time").text if event.find("time") is not None else ""
                
                events.append({
                    "title": title,
                    "country": country,
                    "date": event_date,
                    "time": event_time,
                    "impact": imp,
                    "forecast": event.find("forecast").text if event.find("forecast") is not None else "",
                    "previous": event.find("previous").text if event.find("previous") is not None else ""
                })
        logger.info(f"Parsed {len(events)} High-impact news milestones.")
        return events
    except Exception as e:
        logger.error(f"Error parse Forex Factory calendar: {e}")
        return []


def write_memory(content: str) -> Dict[str, Any]:
    """Appends critical facts into unified flat brain ledger file MEMORY.md."""
    logger.info("Writing updates to unified agent central memory ledger...")
    try:
        mem_file = os.path.join(VAULT_ROOT, "06_AGENT_MEMORY", "MEMORY.md")
        os.makedirs(os.path.dirname(mem_file), exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n\n### Memory Node [{timestamp}]\n- {content}\n"
        
        # Open in append mode
        with open(mem_file, "a", encoding="utf-8") as f:
            f.write(entry)
            
        return {"success": True, "timestamp": timestamp}
    except Exception as e:
        logger.error(f"Failed performing memory bookkeeping: {e}")
        return {"success": False, "error": str(e)}

# ==========================================
# TOOL DISPATCH AND EXECUTION MANAGER
# ==========================================

async def execute_tool_by_name(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Surgically matches names to exact function definitions with safety guards.
    All underlying tool functions are synchronous (use blocking `requests` calls),
    so they are dispatched via run_in_executor to avoid freezing the event loop
    that also serves the SSE chat stream and /health endpoint.
    """
    import asyncio
    import functools

    logger.info(f"[*] Dispatching structured tool: '{tool_name}'")
    loop = asyncio.get_event_loop()

    async def _run(fn, **kwargs):
        return await loop.run_in_executor(None, functools.partial(fn, **kwargs))

    try:
        if tool_name == "read_market_bars":
            return {"success": True, "result": await _run(read_market_bars, **params)}
        elif tool_name == "write_obsidian_note":
            return await _run(write_obsidian_note, **params)
        elif tool_name == "read_obsidian_note":
            return await _run(read_obsidian_note, **params)
        elif tool_name == "search_vault":
            return {"success": True, "result": await _run(search_vault, **params)}
        elif tool_name == "query_knowledge_base":
            return await _run(query_knowledge_base, **params)
        elif tool_name == "run_backtest":
            return await _run(run_backtest, **params)
        elif tool_name == "get_paper_trade_status":
            return await _run(get_paper_trade_status)
        elif tool_name == "send_trade_signal":
            return await _run(send_trade_signal, **params)
        elif tool_name == "draw_on_chart":
            return await _run(draw_on_chart, **params)
        elif tool_name == "get_economic_calendar":
            return {"success": True, "result": await _run(get_economic_calendar)}
        elif tool_name == "write_memory":
            return await _run(write_memory, **params)
        else:
            return {"success": False, "error": f"Tool '{tool_name}' not registered on host."}
    except TypeError as te:
        logger.error(f"Method signature parameters mismatch: {te}")
        return {"success": False, "error": f"Parameters signature mismatch: {str(te)}"}
    except Exception as e:
        logger.error(f"Tool exception caught: {e}")
        return {"success": False, "error": str(e)}


async def process_potential_tool_call_in_text(text: str):
    """
    Seeks markers `[TOOL: name] {json} [/TOOL]` and executes corresponding tools.
    """
    pattern = r"\[TOOL:\s*(\w+)\]\s*(\{[\s\S]*?\})\s*\[/TOOL\]"
    matches = re.finditer(pattern, text)
    
    for match in matches:
        t_name = match.group(1).strip()
        p_str = match.group(2).strip()
        logger.info(f"Detected inline auto-tool execution statement inside output text block: {t_name}")
        
        try:
            params = json.loads(p_str)
            result = await execute_tool_by_name(t_name, params)
            logger.info(f"Auto-tool execution complete. Outcome payload status: {result.get('success')}")
        except Exception as e:
            logger.error(f"Failed parsing/invoking inline tool {t_name}: {e}")

# ==========================================
# FASTAPI ENDPOINT INGESTION API
# ==========================================

@app.get("/health")
async def health():
    """Diagnostic system indices."""
    import asyncio
    ollama_ok = False
    details = "unreachable"
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(None, lambda: requests.get(f"{OLLAMA_HOST}/", timeout=2))
        if resp.status_code == 200 or "Ollama" in resp.text:
            ollama_ok = True
            details = "active"
    except Exception as e:
        details = f"failed to connect ({e})"
        
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "vault_path": VAULT_ROOT,
        "ollama": {
            "status": "online" if ollama_ok else "offline",
            "message": details
        },
        "registered_tools": [
            "read_market_bars",
            "write_obsidian_note",
            "read_obsidian_note",
            "search_vault",
            "query_knowledge_base",
            "run_backtest",
            "get_paper_trade_status",
            "send_trade_signal",
            "draw_on_chart",
            "get_economic_calendar",
            "write_memory"
        ]
    }


@app.post("/tool")
async def execute_tool_endpoint(payload: ToolExecutionPayload):
    """Execution bridge to launch catalog processes programmatically."""
    result = await execute_tool_by_name(payload.tool_name, payload.params)
    return result


@app.post("/chat")
async def stream_chat_endpoint(payload: ChatPayload):
    """
    Channels prompt sequences directly into local Ollama process.
    Streams structured token contents back as clean Server-Sent-Events.
    Processes any included automated tool executions.
    """
    task = payload.task_type or "analysis"
    selected_model = MODEL_MAP.get(task, "Hermes-3")
    logger.info(f"Resolving chat. Task class: '{task}' -> Model: '{selected_model}'")
    
    sys_prompt = load_system_prompt()
    
    # Construct Ollama context format
    messages = [
        {"role": "system", "content": sys_prompt}
    ]
    
    # Inject chat timelines history if parsed inside context metadata
    if payload.context and "history" in payload.context:
        for idx, item in enumerate(payload.context["history"]):
            messages.append({
                "role": item.get("role", "user"),
                "content": item.get("content", "")
            })
            
    messages.append({"role": "user", "content": payload.message})

    async def sse_event_generator():
        target_endpoint = f"{OLLAMA_HOST}/api/chat"
        req_params = {
            "model": selected_model,
            "messages": messages,
            "stream": True
        }
        
        full_tokens_buff = []
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream("POST", target_endpoint, json=req_params) as r:
                    if r.status_code != 200:
                        yield f"data: Ollama returned status error code: {r.status_code}\n\n"
                        return
                        
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        try:
                            line_data = json.loads(line)
                            tok_val = line_data.get("message", {}).get("content", "")
                            if tok_val:
                                full_tokens_buff.append(tok_val)
                                # Stream tokens to caller
                                yield f"data: {tok_val}\n\n"
                        except json.JSONDecodeError:
                            pass # bypass structural line feeds
                            
                # Fully received. Parse outputs sequentially for trigger annotations
                accumulated_text = "".join(full_tokens_buff)
                await process_potential_tool_call_in_text(accumulated_text)
                
                # Suffix complete signal
                yield "data: [DONE]\n\n"
            except httpx.RequestError as exc:
                logger.error(f"Ollama network communication exception: {exc}")
                yield f"data: [Host Ollama Error] {str(exc)}\n\n"
            except Exception as exc:
                logger.error(f"Unmanaged exception in token stream: {exc}")
                yield f"data: [Host Stream Failure] {str(exc)}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    logger.info("=========================================================================")
    logger.info("Hermes Host RPC Server is booting...")
    logger.info(f"Targeting active Ollama process channel: {OLLAMA_HOST}")
    logger.info(f"Obsidian Vault structural root path: {VAULT_ROOT}")
    logger.info("=========================================================================")
    uvicorn.run(app, host="0.0.0.0", port=7778, log_level="warning")
