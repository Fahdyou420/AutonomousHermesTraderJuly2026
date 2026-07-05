"""
Hermes Trading MCP Server
==========================
Exposes the Hermes trading microservices as MCP tools that the
Nous Research Hermes Desktop Agent can call natively.

Register in ~/.hermes/config.yaml:

mcp_servers:
  hermes_trading:
    url: http://localhost:7779/mcp

Run with: python hermes_mcp_server.py
Or:       powershell -File scripts/start_mcp_server.ps1
"""
import os, json, requests, logging
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
load_dotenv(override=True)  # override=True ensures .env wins over stale system/user env vars
import uvicorn

app = FastAPI(title="Hermes Trading MCP Server", version="1.1")

# ── Full configuration surface — every knob overridable via .env ─────────────
# When running natively on the Windows host, internal Docker DNS (e.g. mt5_bridge) 
# won't resolve. We map them to localhost where the ports are published.
def _local_url(url: str) -> str:
    import re
    return re.sub(r'http://([a-zA-Z0-9_]+):', r'http://localhost:', url)

MT5_URL     = _local_url(os.getenv("MT5_BRIDGE_URL",   "http://localhost:5558"))
PAPER_URL   = _local_url(os.getenv("PAPER_TRADER_URL", "http://localhost:5561"))
PREPROC_URL = _local_url(os.getenv("PREPROCESSOR_URL", "http://localhost:5559"))
BACKTEST_URL= _local_url(os.getenv("BACKTESTER_URL",   "http://localhost:5560"))
MCP_URL     = _local_url(os.getenv("MCP_BRIDGE_URL",   "http://localhost:5562"))

# Where Hermes Desktop looks for its own config — used so skills created via
# natural language land exactly where Hermes Desktop will find them.
HERMES_HOME_DIR   = Path(os.getenv("HERMES_HOME_DIR",   str(Path.home() / ".hermes")))
HERMES_SKILLS_DIR = Path(os.getenv("HERMES_SKILLS_DIR",  str(HERMES_HOME_DIR / "skills" / "trading")))
OBSIDIAN_VAULT_ROOT = os.getenv("OBSIDIAN_VAULT_ROOT", str(Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "hermes" / "obsidian"))

# Default risk parameters — every trade signal is validated against these
# unless overridden by the agent per-call. Central place to tune risk posture.
DEFAULT_MAX_RISK_PCT   = float(os.getenv("MAX_RISK_PCT", "1.0"))
DEFAULT_MAX_DAILY_DD   = float(os.getenv("MAX_DAILY_DD", "3.0"))
DEFAULT_INSTRUMENT     = os.getenv("HERMES_INSTRUMENT", "XAUUSD")
DEFAULT_MTF_LIST       = os.getenv("HERMES_MTF_LIST", "M5,M15,H1,H4,D1").split(",")

LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
LOG_DIR   = Path(os.getenv("HERMES_LOG_DIR", str(Path.home() / "HermesLogs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [MCP] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "mcp_server.log", encoding="utf-8")
    ]
)
log = logging.getLogger("hermes_mcp")
log.info(f"Config loaded — vault: {OBSIDIAN_VAULT_ROOT} | skills: {HERMES_SKILLS_DIR} | "
         f"risk: {DEFAULT_MAX_RISK_PCT}% | dd_halt: {DEFAULT_MAX_DAILY_DD}% | "
         f"instrument: {DEFAULT_INSTRUMENT} | mtf: {DEFAULT_MTF_LIST}")


def _get(url, timeout=5):
    try:
        r = requests.get(url, timeout=timeout)
        return r.json() if r.ok else {"error": f"{r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def _post(url, payload, timeout=30):
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r.json() if r.ok else {"error": f"{r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


TOOLS = [
    {"name": "get_market_bars",
     "description": "Get OHLCV bars for an instrument. Works weekends via yfinance fallback. Returns list of {timestamp, open, high, low, close, volume}.",
     "inputSchema": {"type": "object", "properties": {
         "instrument": {"type": "string", "default": "XAUUSD", "description": "XAUUSD, BTCUSD, EURUSD etc"},
         "timeframe":  {"type": "string", "default": "M15", "description": "M1 M5 M15 M30 H1 H4 D1"},
         "n":          {"type": "integer", "default": 200}}}},

    {"name": "get_market_bars_mtf",
     "description": "Get OHLCV bars across MULTIPLE timeframes in a single call for true multi-timeframe analysis (e.g. HTF bias on H4/D1, LTF entry on M5/M15). Returns a dict keyed by timeframe. The EA maintains a live multi-timeframe bundle (M5/M15/H1/H4/D1) refreshed automatically, independent of which chart it's attached to.",
     "inputSchema": {"type": "object", "properties": {
         "instrument": {"type": "string", "default": "XAUUSD"},
         "timeframes": {"type": "array", "items": {"type": "string"},
                        "default": ["M15", "H1", "H4", "D1"],
                        "description": "List of timeframes to fetch, e.g. ['M15','H1','H4','D1']"},
         "n":          {"type": "integer", "default": 200, "description": "Bars per timeframe"}}}},

    {"name": "get_account_state",
     "description": "Current account balance, equity, margin, profit from MT5.",
     "inputSchema": {"type": "object", "properties": {}}},

    {"name": "get_open_positions",
     "description": "List open paper trading positions with ticket, symbol, direction, lots, prices, P&L.",
     "inputSchema": {"type": "object", "properties": {}}},

    {"name": "get_trading_stats",
     "description": "Paper trading stats: win rate, profit factor, average R:R, max drawdown, total trades.",
     "inputSchema": {"type": "object", "properties": {}}},

    {"name": "get_trade_history",
     "description": "Last N closed paper trades with entry/exit prices, P&L, direction.",
     "inputSchema": {"type": "object", "properties": {
         "n": {"type": "integer", "default": 20}}}},

    {"name": "send_paper_trade",
     "description": "Send a paper trade signal. Passes through the risk gatekeeper (1% max risk, drawdown checks). Use only for setups that passed backtesting.",
     "inputSchema": {"type": "object", "required": ["direction", "entry_price", "sl", "tp", "instrument"],
         "properties": {
             "instrument":  {"type": "string"},
             "direction":   {"type": "string", "enum": ["BUY", "SELL"]},
             "entry_price": {"type": "number"},
             "sl":          {"type": "number"},
             "tp":          {"type": "number"},
             "lots":        {"type": "number", "default": 0.01},
             "setup_type":  {"type": "string"},
             "timeframe":   {"type": "string", "default": "M15"},
             "notes":       {"type": "string"}}}},

    {"name": "close_position",
     "description": "Close an open paper position by ticket ID.",
     "inputSchema": {"type": "object", "required": ["ticket"],
         "properties": {"ticket": {"type": "integer"}}}},

    {"name": "run_backtest",
     "description": "Run a strategy backtest. Returns win rate, profit factor, max drawdown, sample trades.",
     "inputSchema": {"type": "object", "required": ["instrument", "strategy_type"],
         "properties": {
             "instrument":    {"type": "string", "default": "XAUUSD"},
             "timeframe":     {"type": "string", "default": "M15"},
             "strategy_type": {"type": "string", "description": "smc_ob_entry | smc_fvg_fill | smc_liquidity_sweep"},
             "entry_logic":   {"type": "string"},
             "sl_type":       {"type": "string", "default": "structure"},
             "tp_type":       {"type": "string", "default": "fvg_fill"},
             "risk_pct":      {"type": "number", "default": 1.0},
             "lookback_bars": {"type": "integer", "default": 500}}}},

    {"name": "get_smc_analysis",
     "description": "Pre-computed SMC analysis: Fair Value Gaps, Order Blocks, BOS, CHoCH, liquidity.",
     "inputSchema": {"type": "object", "properties": {
         "instrument": {"type": "string", "default": "XAUUSD"},
         "timeframe":  {"type": "string", "default": "M15"},
         "n":          {"type": "integer", "default": 300}}}},

    {"name": "get_system_status",
     "description": "Health of all trading services and whether the MT5 EA is actively connected.",
     "inputSchema": {"type": "object", "properties": {}}},

    {"name": "draw_on_chart",
     "description": "Draw a single object on the MT5 chart. Types: rect, hline, trendline, arrow, label. Colors: green, red, blue, orange, cyan, magenta, yellow.",
     "inputSchema": {"type": "object", "required": ["type", "id", "cmd"],
         "properties": {
             "type":   {"type": "string"},
             "cmd":    {"type": "string", "default": "draw"},
             "id":     {"type": "string"},
             "price1": {"type": "number"},
             "price2": {"type": "number"},
             "time1":  {"type": "integer"},
             "time2":  {"type": "integer"},
             "color":  {"type": "string", "default": "blue"},
             "label":  {"type": "string", "default": ""},
             "width":  {"type": "integer", "default": 1}}}},

    {"name": "visualise_analysis",
     "description": "Fetch live SMC analysis and draw ALL detected structures on the MT5 chart at once: FVGs as boxes, Order Blocks as shaded zones, BOS/CHoCH as labelled lines, liquidity as dotted lines, and current bias label. Call this after every scan to show your work visually.",
     "inputSchema": {"type": "object", "properties": {
         "instrument": {"type": "string", "default": "XAUUSD"},
         "timeframe":  {"type": "string", "default": "M15"},
         "n":          {"type": "integer", "default": 300},
         "clear_first":{"type": "boolean", "default": True, "description": "Clear previous agent drawings before painting new ones"},
         "bias":       {"type": "string", "default": "NEUTRAL", "description": "Current bias to show in chart corner label"}}}},

    {"name": "draw_trade_signal",
     "description": "Paint a trade signal on the MT5 chart: entry arrow, SL line, TP line, and notes tooltip. Call this every time a paper trade is sent so it's visible on the chart.",
     "inputSchema": {"type": "object", "required": ["direction", "entry_price", "sl", "tp"],
         "properties": {
             "signal_id":   {"type": "string"},
             "direction":   {"type": "string", "enum": ["BUY", "SELL"]},
             "entry_price": {"type": "number"},
             "sl":          {"type": "number"},
             "tp":          {"type": "number"},
             "entry_time":  {"type": "integer", "description": "Unix timestamp"},
             "notes":       {"type": "string", "default": ""}}}},

    {"name": "run_full_backtest",
     "description": "Run a complete backtest: 1) request fresh bars from MT5 (or yfinance if offline), 2) run the Python SMC backtest engine on them, 3) return full results with equity curve and trade list. More accurate than run_backtest because it always uses the most recent data.",
     "inputSchema": {"type": "object", "required": ["instrument", "strategy_type"],
         "properties": {
             "instrument":    {"type": "string", "default": "XAUUSD"},
             "timeframe":     {"type": "string", "default": "M15"},
             "strategy_type": {"type": "string", "description": "smc_ob_entry | smc_fvg_fill | smc_liquidity_sweep"},
             "entry_logic":   {"type": "string", "description": "Natural language description of entry conditions"},
             "sl_type":       {"type": "string", "default": "structure"},
             "tp_type":       {"type": "string", "default": "fvg_fill"},
             "risk_pct":      {"type": "number", "default": 1.0},
             "lookback_bars": {"type": "integer", "default": 1000},
             "session_filter":{"type": "array", "items": {"type": "string"},
                               "default": ["london", "newyork", "overlap"],
                               "description": "Sessions to trade: asian, london, newyork, overlap"}}}}
    ,
    {"name": "create_hermes_skill",
     "description": "Create a new Hermes Desktop skill from a natural-language trading strategy description. Writes a proper skill markdown file directly to ~/.hermes/skills/ so it becomes immediately callable (e.g. '/skill my_new_strategy'). Use this whenever the person describes a new strategy or trading behavior in plain English — turn it into a durable, reusable skill rather than a one-off analysis. Pair with create_strategy to also give the skill a backtestable Python implementation.",
     "inputSchema": {"type": "object", "required": ["skill_name", "description", "steps"],
         "properties": {
             "skill_name": {"type": "string", "description": "snake_case unique name, e.g. 'asian_range_breakout'"},
             "description": {"type": "string", "description": "One-line summary of what the skill does"},
             "steps": {"type": "string", "description": "Full step-by-step markdown body describing exactly what the agent should do when this skill runs — data to fetch, conditions to check, tools to call, decisions to make. Write this as clear numbered instructions, the same way you'd write any other Hermes skill."},
             "tags": {"type": "array", "items": {"type": "string"}, "default": ["trading", "custom"]},
             "linked_strategy": {"type": "string", "description": "Optional: name of a backtester strategy (from create_strategy) this skill should reference for backtesting/verdict logic"}}}},

    {"name": "list_hermes_skills",
     "description": "List all skills currently installed in ~/.hermes/skills/, including ones created via natural language and the built-in smc_trading_cycle skill.",
     "inputSchema": {"type": "object", "properties": {}}},

    {"name": "delete_hermes_skill",
     "description": "Delete a skill file from ~/.hermes/skills/ by name.",
     "inputSchema": {"type": "object", "required": ["skill_name"],
         "properties": {"skill_name": {"type": "string"}}}},

    {"name": "get_hermes_config",
     "description": "Return the current full configuration: models, vault path, skills path, log path, risk parameters, default instrument, and MTF list. Use this to check or report current settings before changing anything.",
     "inputSchema": {"type": "object", "properties": {}}},

    {"name": "list_strategies",
     "description": "List all available backtest strategies: built-in SMC strategies plus any custom ones the agent has created. Shows name, description, valid sessions, and source.",
     "inputSchema": {"type": "object", "properties": {}}},

    {"name": "create_strategy",
     "description": "Create a new custom trading strategy plugin in Python. Saved to disk and immediately available for backtesting. Must inherit BaseStrategy and implement find_signal(). After creating, always test with run_full_backtest.",
     "inputSchema": {"type": "object", "required": ["name", "code"],
         "properties": {
             "name": {"type": "string", "description": "Unique snake_case name e.g. ema_cross_ob"},
             "code": {"type": "string", "description": "Complete Python strategy plugin source code"},
             "description": {"type": "string"}}}},

    {"name": "delete_strategy",
     "description": "Delete a custom strategy by name. Cannot delete built-in strategies.",
     "inputSchema": {"type": "object", "required": ["name"],
         "properties": {"name": {"type": "string"}}}},

    {"name": "get_strategy_template",
     "description": "Get a Python template for a new custom strategy. Use this as a starting point when creating strategies with create_strategy.",
     "inputSchema": {"type": "object", "properties": {
         "template_type": {"type": "string",
                           "enum": ["smc", "indicator", "hybrid"],
                           "default": "smc",
                           "description": "smc=structure-based, indicator=EMA/RSI-based, hybrid=both"}}}}
]


def _yfinance_bars(instrument, timeframe, n):
    import yfinance as yf
    ticker_map = {"XAUUSD": "GC=F", "BTCUSD": "BTC-USD", "BTCUSDT": "BTC-USD",
                  "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X"}
    tf_map = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
              "H1": "60m", "H4": "1h", "D1": "1d", "W1": "1wk"}
    ticker = ticker_map.get(instrument.upper(), instrument)
    yf_tf  = tf_map.get(timeframe.upper(), "15m")
    period = "5d" if yf_tf in ["1m","5m","15m","30m"] else "60d"
    df = yf.download(ticker, period=period, interval=yf_tf, progress=False, auto_adjust=True)
    if df.empty:
        return {"error": f"No yfinance data for {ticker}"}
    bars = []
    for ts, row in df.tail(n).iterrows():
        def _scalar(v):
            try:
                return float(v)
            except Exception:
                return float(v.iloc[0])
        bars.append({"timestamp": int(ts.timestamp()), "instrument": instrument,
                     "timeframe": timeframe, "open": _scalar(row["Open"]),
                     "high": _scalar(row["High"]), "low": _scalar(row["Low"]),
                     "close": _scalar(row["Close"]), "volume": int(_scalar(row.get("Volume", 0))),
                     "source": "yfinance"})
    return bars


def handle_tool(name, args):
    if name == "get_market_bars":
        instr = args.get("instrument", "XAUUSD")
        tf    = args.get("timeframe", "M15")
        n     = int(args.get("n", 200))
        data  = _get(f"{MT5_URL}/latest_bars?instrument={instr}&tf={tf}&n={n}")
        if isinstance(data, list) and len(data) > 0:
            return data
        try:
            return _yfinance_bars(instr, tf, n)
        except ImportError:
            return {"error": "MT5 offline and yfinance not installed. Run: pip install yfinance"}
        except Exception as e:
            return {"error": f"Both MT5 and yfinance failed: {e}"}

    elif name == "get_market_bars_mtf":
        instr = args.get("instrument", DEFAULT_INSTRUMENT)
        tfs   = args.get("timeframes", ["M15", "H1", "H4", "D1"])
        n     = int(args.get("n", 200))
        result = {}
        for tf in tfs:
            result[tf] = handle_tool("get_market_bars", {"instrument": instr, "timeframe": tf, "n": n})
        return result

    elif name == "get_account_state":
        return _get(f"{MT5_URL}/account_state")

    elif name == "get_open_positions":
        return _get(f"{PAPER_URL}/positions")

    elif name == "get_trading_stats":
        return _get(f"{PAPER_URL}/stats")

    elif name == "get_trade_history":
        n = int(args.get("n", 20))
        return _get(f"{PAPER_URL}/history?n={n}")

    elif name == "send_paper_trade":
        ep = float(args.get("entry_price", 0))
        sl = float(args.get("sl", 0))
        tp = float(args.get("tp", 0))
        rr = abs((tp - ep) / (ep - sl + 0.0001)) if ep != sl else 0
        signal = {
            "signal_id":   f"mcp_{int(datetime.utcnow().timestamp())}",
            "timestamp":   int(datetime.utcnow().timestamp()),
            "instrument":  args.get("instrument", "XAUUSD"),
            "direction":   args.get("direction", "BUY").lower(),
            "entry_price": ep, "entry_type": "market",
            "sl": sl, "tp": tp,
            "lots":        float(args.get("lots", 0.01)),
            "timeframe":   args.get("timeframe", "M15"),
            "strategy_id": f"hermes_mcp_{datetime.utcnow().strftime('%Y%m%d_%H%M')}",
            "setup_type":  args.get("setup_type", "SMC"),
            "session":     "auto", "mode": "paper",
            "confidence":  "high", "r_ratio": round(rr, 2),
            "agent_notes": args.get("notes", ""), "status": "pending"
        }
        return _post(f"{MCP_URL}/signal", signal)

    elif name == "close_position":
        return _post(f"{PAPER_URL}/close/{args.get('ticket')}", {})

    elif name == "run_backtest":
        return _post(f"{BACKTEST_URL}/backtest", {
            "strategy_id":   args.get("strategy_id", f"bt_{int(datetime.utcnow().timestamp())}"),
            "name":          args.get("name", "Manual Backtest"),
            "instrument":    args.get("instrument", "XAUUSD"),
            "timeframe":     args.get("timeframe", "M15"),
            "strategy_type": args.get("strategy_type", "smc_ob_entry"),
            "entry_logic":   args.get("entry_logic", ""),
            "sl_type":       args.get("sl_type", "structure"),
            "tp_type":       args.get("tp_type", "fvg_fill"),
            "risk_pct":      float(args.get("risk_pct", 1.0)),
            "lookback_bars": int(args.get("lookback_bars", 500))
        }, timeout=120)

    elif name == "get_smc_analysis":
        instr = args.get("instrument", "XAUUSD")
        tf    = args.get("timeframe", "M15")
        n     = int(args.get("n", 300))
        return _get(f"{PREPROC_URL}/smc_analysis?instrument={instr}&tf={tf}&n={n}")

    elif name == "get_system_status":
        def chk(url):
            try: return "online" if requests.get(url, timeout=2).ok else "error"
            except: return "offline"
        mt5_h = _get(f"{MT5_URL}/health")
        return {
            "mt5_bridge":   chk(f"{MT5_URL}/health"),
            "ea_connected": mt5_h.get("ea_connected", False) if isinstance(mt5_h, dict) else False,
            "paper_trader": chk(f"{PAPER_URL}/health"),
            "preprocessor": chk(f"{PREPROC_URL}/health"),
            "backtester":   chk(f"{BACKTEST_URL}/health"),
            "mcp_bridge":   chk(f"{MCP_URL}/health"),
            "timestamp":    datetime.utcnow().isoformat() + "Z"
        }

    elif name == "draw_on_chart":
        return _post(f"{MCP_URL}/draw", args)

    elif name == "visualise_analysis":
        instr       = args.get("instrument", "XAUUSD")
        tf          = args.get("timeframe", "M15")
        n           = int(args.get("n", 300))
        clear_first = args.get("clear_first", True)
        bias        = args.get("bias", "NEUTRAL")
        drawn       = []

        # Clear previous drawings
        if clear_first:
            _post(f"{MCP_URL}/draw", {"type": "rect", "cmd": "clear", "id": "all"})

        # Get SMC analysis
        smc = _get(f"{PREPROC_URL}/smc_analysis?instrument={instr}&tf={tf}&n={n}")
        if not isinstance(smc, dict):
            return {"error": "SMC analysis unavailable", "drawn": 0}

        # Draw FVGs
        for fvg in (smc.get("fvg") or []):
            if fvg.get("filled"): continue  # skip already-filled gaps
            obj = {
                "type": "fvg", "cmd": "draw",
                "id":    fvg.get("id", f"fvg_{len(drawn)}"),
                "price1": fvg.get("high", 0),
                "price2": fvg.get("low", 0),
                "time1":  fvg.get("time1", 0),
                "time2":  fvg.get("time2", 0),
                "direction": fvg.get("type", "bullish"),
                "color": "blue" if fvg.get("type") == "bullish" else "orange",
                "label": ("Bullish" if fvg.get("type") == "bullish" else "Bearish") + " FVG"
            }
            _post(f"{MCP_URL}/draw", obj)
            drawn.append(f"FVG_{fvg.get('id','')}")

        # Draw Order Blocks
        for ob in (smc.get("order_blocks") or []):
            if ob.get("mitigated"): continue
            obj = {
                "type": "ob", "cmd": "draw",
                "id":    ob.get("id", f"ob_{len(drawn)}"),
                "price1": ob.get("high", 0),
                "price2": ob.get("low", 0),
                "time1":  ob.get("time1", ob.get("time", 0)),
                "time2":  ob.get("time2", ob.get("time", 0) + 3600 * 4),
                "direction": ob.get("type", "bullish"),
                "color": "green" if ob.get("type") == "bullish" else "red",
                "label": ("Bullish" if ob.get("type") == "bullish" else "Bearish") + " OB"
            }
            _post(f"{MCP_URL}/draw", obj)
            drawn.append(f"OB_{ob.get('id','')}")

        # Draw BOS
        for bos in (smc.get("bos") or [])[-5:]:  # last 5 only
            _post(f"{MCP_URL}/draw", {
                "type": "bos", "cmd": "draw",
                "id":    bos.get("id", f"bos_{len(drawn)}"),
                "price1": bos.get("level", bos.get("price", 0)),
                "time1":  bos.get("timestamp", bos.get("time", 0)),
                "color": "yellow", "label": "BOS"
            })
            drawn.append(f"BOS_{bos.get('id','')}")

        # Draw CHoCH
        for choch in (smc.get("choch") or [])[-3:]:
            _post(f"{MCP_URL}/draw", {
                "type": "choch", "cmd": "draw",
                "id":    choch.get("id", f"choch_{len(drawn)}"),
                "price1": choch.get("level", choch.get("price", 0)),
                "time1":  choch.get("timestamp", choch.get("time", 0)),
                "color": "cyan", "label": "CHoCH"
            })
            drawn.append(f"CHoCH_{choch.get('id','')}")

        # Draw Liquidity
        for liq in (smc.get("liquidity") or [])[-8:]:
            _post(f"{MCP_URL}/draw", {
                "type": "liquidity", "cmd": "draw",
                "id":    liq.get("id", f"liq_{len(drawn)}"),
                "price1": liq.get("price", liq.get("level", 0)),
                "time1":  liq.get("timestamp", liq.get("time", 0)),
                "direction": "bullish" if liq.get("type") == "high" else "bearish",
                "color": "magenta",
                "label": "BSL" if liq.get("type") == "high" else "SSL"
            })
            drawn.append(f"LIQ_{liq.get('id','')}")

        # Draw bias label (sent as a special signal command)
        _post(f"{MCP_URL}/draw", {
            "type": "signal", "cmd": "update_bias",
            "id": "bias_label", "bias": bias
        })

        return {
            "success": True,
            "drawn": len(drawn),
            "objects": drawn,
            "fvgs": len(smc.get("fvg") or []),
            "order_blocks": len(smc.get("order_blocks") or []),
            "bos": len(smc.get("bos") or []),
            "choch": len(smc.get("choch") or []),
            "liquidity": len(smc.get("liquidity") or [])
        }

    elif name == "draw_trade_signal":
        direction  = args.get("direction", "BUY")
        entry      = float(args.get("entry_price", 0))
        sl         = float(args.get("sl", 0))
        tp         = float(args.get("tp", 0))
        sig_id     = args.get("signal_id", f"sig_{int(datetime.utcnow().timestamp())}")
        entry_time = int(args.get("entry_time", datetime.utcnow().timestamp()))
        notes      = args.get("notes", "")

        _post(f"{MCP_URL}/draw", {
            "type": "signal", "cmd": "draw",
            "id":          sig_id,
            "direction":   direction,
            "entry_price": entry,
            "sl":          sl,
            "tp":          tp,
            "time1":       entry_time,
            "notes":       notes,
            "color":       "green" if direction == "BUY" else "red"
        })
        return {
            "success": True,
            "signal_id": sig_id,
            "drawn": {"entry": entry, "sl": sl, "tp": tp,
                      "rr": round(abs(tp - entry) / max(abs(entry - sl), 0.0001), 2)}
        }

    elif name == "run_full_backtest":
        instr    = args.get("instrument", "XAUUSD")
        tf       = args.get("timeframe", "M15")
        n        = int(args.get("lookback_bars", 1000))
        risk_pct = float(args.get("risk_pct", 1.0))
        sessions = args.get("session_filter", ["london", "newyork", "overlap"])

        # Step 1: Get fresh bars (MT5 or yfinance)
        bars = handle_tool("get_market_bars", {"instrument": instr, "timeframe": tf, "n": n})
        if isinstance(bars, dict) and "error" in bars:
            return {"error": f"Could not get bars: {bars['error']}"}
        if not bars or len(bars) < 50:
            return {"error": f"Insufficient data: only {len(bars) if bars else 0} bars"}

        # Step 2: Run backtest via backtester service with full config
        import uuid as _uuid
        config = {
            "strategy_id":      f"auto_{instr}_{tf}_{_uuid.uuid4().hex[:8]}",
            "name":             f"Hermes {args.get('strategy_type','smc_ob_entry')} on {instr} {tf}",
            "instrument":       instr,
            "timeframe":        tf,
            "session_filter":   sessions,
            "entry_logic":      {"type": args.get("strategy_type", "smc_ob_entry"),
                                 "description": args.get("entry_logic", "")},
            "sl_logic":         {"type": args.get("sl_type", "structure"), "value": 15},
            "tp_logic":         {"type": args.get("tp_type", "fvg_fill"), "value": 30},
            "risk_pct":         risk_pct,
            "max_trades_per_day": 2,
            "spread_gate_pips": 25,
            "date_from":        "",
            "date_to":          ""
        }
        result = _post(f"{BACKTEST_URL}/backtest", config, timeout=180)
        if not result:
            return {"error": "Backtester service unavailable or timed out"}

        # Step 3: Add verdict
        wr = float(result.get("win_rate", 0))
        pf = float(result.get("profit_factor", 0))
        verdict = "APPROVED" if wr >= 0.52 and pf >= 1.3 else "REJECTED"
        result["verdict"] = verdict
        result["verdict_reason"] = (
            f"Win rate {wr:.1%} ({'>=52%' if wr>=0.52 else '<52%'}), "
            f"Profit factor {pf:.2f} ({'>=1.3' if pf>=1.3 else '<1.3'})"
        )
        result["bars_used"] = len(bars)
        return result

    elif name == "list_strategies":
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from services.backtester.strategy_loader import list_strategies
            return {"strategies": list_strategies(), "count": len(list_strategies())}
        except Exception as e:
            return {"error": str(e)}

    elif name == "create_strategy":
        strategy_name = args.get("name", "").strip()
        code          = args.get("code", "").strip()
        if not strategy_name or not code:
            return {"error": "Both 'name' and 'code' are required"}
        try:
            from services.backtester.strategy_loader import save_strategy
            ok, msg = save_strategy(strategy_name, code)
            if ok:
                return {"success": True, "saved_to": msg,
                        "message": f"Strategy '{strategy_name}' saved. Now test it with run_full_backtest using strategy_type='{strategy_name}'."}
            return {"success": False, "error": msg}
        except Exception as e:
            return {"error": str(e)}

    elif name == "delete_strategy":
        strategy_name = args.get("name", "").strip()
        if not strategy_name:
            return {"error": "'name' is required"}
        try:
            from services.backtester.strategy_loader import delete_strategy
            ok, msg = delete_strategy(strategy_name)
            return {"success": ok, "message": msg}
        except Exception as e:
            return {"error": str(e)}

    elif name == "get_strategy_template":
        template_type = args.get("template_type", "smc")

        if template_type == "indicator":
            code = '''from typing import Dict, Any, Optional, List
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from services.backtester.strategies.base import BaseStrategy
from services.preprocessor.indicators import ema, rsi, atr

class MyIndicatorStrategy(BaseStrategy):
    name        = "my_indicator_strategy"   # change this — must be unique
    description = "EMA cross + RSI filter entry strategy"
    author      = "Hermes Agent"
    version     = "1.0"
    valid_sessions = ["london", "newyork", "overlap"]
    min_bars    = 60

    def find_signal(self, bars, i, smc, triggered_ids):
        if i < self.min_bars:
            return None

        bar   = bars[i]
        close = float(bar.get("close", 0))
        ts    = int(bar.get("timestamp", 0))

        # Compute indicators up to bar i (no lookahead)
        ema_fast = ema(bars[:i+1], 9)
        ema_slow = ema(bars[:i+1], 21)
        rsi14    = rsi(bars[:i+1], 14)

        if not ema_fast or not ema_slow or not rsi14:
            return None

        ef_now  = ema_fast[-1]; ef_prev = ema_fast[-2]
        es_now  = ema_slow[-1]; es_prev = ema_slow[-2]
        rsi_now = rsi14[-1]

        setup_id = f"ema_cross_{ts}"
        if setup_id in triggered_ids:
            return None

        # EMA bullish cross + RSI not overbought
        if ef_prev <= es_prev and ef_now > es_now and rsi_now < 65:
            triggered_ids.add(setup_id)
            return {"direction": "long", "entry_price": close,
                    "setup_id": setup_id, "notes": f"EMA9 crossed above EMA21, RSI={rsi_now:.1f}"}

        # EMA bearish cross + RSI not oversold
        if ef_prev >= es_prev and ef_now < es_now and rsi_now > 35:
            triggered_ids.add(setup_id)
            return {"direction": "short", "entry_price": close,
                    "setup_id": setup_id, "notes": f"EMA9 crossed below EMA21, RSI={rsi_now:.1f}"}

        return None
'''
        elif template_type == "hybrid":
            code = '''from typing import Dict, Any, Optional, List
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from services.backtester.strategies.base import BaseStrategy
from services.preprocessor.indicators import ema, atr

class MyHybridStrategy(BaseStrategy):
    """
    Hybrid: SMC structure (OB) as the zone, EMA trend as the filter.
    Only take OB entries when price is on the correct side of EMA200.
    """
    name        = "my_hybrid_strategy"   # change this
    description = "Order Block entry filtered by EMA200 trend direction"
    author      = "Hermes Agent"
    version     = "1.0"
    valid_sessions = ["london", "newyork", "overlap"]
    min_bars    = 210

    def find_signal(self, bars, i, smc, triggered_ids):
        if i < self.min_bars:
            return None

        bar   = bars[i]
        ts    = int(bar.get("timestamp", 0))
        high  = float(bar.get("high", 0))
        low   = float(bar.get("low", 0))
        close = float(bar.get("close", 0))

        ema200 = ema(bars[:i+1], 200)
        if not ema200:
            return None
        trend_up = close > ema200[-1]

        for ob in smc.get("order_blocks", []):
            if ob["timestamp"] >= ts:     continue
            if ob["id"] in triggered_ids: continue

            oh, ol = ob["high"], ob["low"]

            if ob["type"] == "bullish" and trend_up and low <= oh and close >= ol:
                triggered_ids.add(ob["id"])
                return {"direction": "long", "entry_price": oh,
                        "setup_id": ob["id"],
                        "notes": f"Bullish OB + above EMA200 ({ema200[-1]:.2f})"}

            if ob["type"] == "bearish" and not trend_up and high >= ol and close <= oh:
                triggered_ids.add(ob["id"])
                return {"direction": "short", "entry_price": ol,
                        "setup_id": ob["id"],
                        "notes": f"Bearish OB + below EMA200 ({ema200[-1]:.2f})"}

        return None
'''
        else:  # smc default
            code = '''from typing import Dict, Any, Optional, List
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from services.backtester.strategies.base import BaseStrategy

class MyCustomSMCStrategy(BaseStrategy):
    """
    Custom SMC strategy template.
    Edit find_signal() to define your entry logic.
    The engine handles SL/TP, lot sizing, and risk management automatically.
    """
    name        = "my_custom_smc"    # REQUIRED — change to a unique snake_case name
    description = "My custom SMC strategy"
    author      = "Hermes Agent"
    version     = "1.0"
    valid_sessions = ["london", "newyork", "overlap"]
    min_bars    = 50

    def find_signal(self, bars, i, smc, triggered_ids):
        """
        bars      : full bar list, bars[i] is current
        i         : current bar index (bars[:i] are historical — no lookahead)
        smc       : {"fvg": [...], "order_blocks": [...], "bos": [...],
                     "choch": [...], "liquidity": [...]}
        triggered_ids : set of structure IDs already used — add yours here

        Return {"direction": "long"|"short", "entry_price": float,
                "setup_id": str, "notes": str}
        or None to skip this bar.
        """
        bar   = bars[i]
        ts    = int(bar.get("timestamp", 0))
        high  = float(bar.get("high", 0))
        low   = float(bar.get("low", 0))
        close = float(bar.get("close", 0))

        # --- YOUR ENTRY LOGIC HERE ---
        # Example: buy when price touches a bullish FVG that has not been filled
        for fvg in smc.get("fvg", []):
            if fvg["time2"] >= ts:          continue  # structure not yet formed
            if fvg["id"] in triggered_ids:  continue  # already used
            if fvg.get("filled"):           continue  # already mitigated

            if fvg["type"] == "bullish" and low <= fvg["high"] and close >= fvg["low"]:
                triggered_ids.add(fvg["id"])
                return {
                    "direction":   "long",
                    "entry_price": fvg["high"],
                    "setup_id":    fvg["id"],
                    "notes":       "Custom: bullish FVG touch"
                }

        return None  # no signal this bar
'''
        return {"template_type": template_type, "code": code,
                "instructions": "Fill in your logic, change the 'name' attribute to something unique, then call create_strategy with this code."}

    elif name == "create_hermes_skill":
        skill_name  = args.get("skill_name", "").strip()
        description = args.get("description", "").strip()
        steps       = args.get("steps", "").strip()
        tags        = args.get("tags", ["trading", "custom"])
        linked      = args.get("linked_strategy", "")

        if not skill_name or not steps:
            return {"error": "'skill_name' and 'steps' are required"}

        safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in skill_name)

        linked_block = ""
        if linked:
            linked_block = (f"\n## Linked Backtest Strategy\n\n"
                           f"This skill's setups should be validated with `run_full_backtest` "
                           f"using `strategy_type: \"{linked}\"` before any live paper trade signal "
                           f"is sent. Require win rate > 52% and profit factor > 1.3 before acting.\n")

        content = f"""---
name: {safe_name}
description: {description}
version: "1.0"
author: Hermes Agent (created via natural language)
tags: {json.dumps(tags)}
created: {datetime.utcnow().isoformat()}Z
---

# {skill_name.replace('_', ' ').title()}

{description}

## Steps

{steps}
{linked_block}
## Available Tools

This skill has access to all hermes_trading MCP tools:
- get_market_bars, get_market_bars_mtf — price data (single or multi-timeframe)
- get_smc_analysis, visualise_analysis — SMC structure detection and charting
- get_account_state, get_open_positions, get_trading_stats, get_trade_history
- send_paper_trade, close_position, draw_trade_signal
- run_full_backtest, list_strategies, create_strategy — strategy testing
- get_system_status — health check before acting

## Notes

Created from a natural-language description. Edit this file directly in
~/.hermes/skills/{safe_name}.md to refine behavior, or ask the agent to
recreate it with create_hermes_skill using an updated description.
"""

        try:
            HERMES_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            skill_path = HERMES_SKILLS_DIR / f"{safe_name}.md"
            skill_path.write_text(content, encoding="utf-8")
            log.info(f"Skill created: {skill_path}")
            return {
                "success": True,
                "skill_name": safe_name,
                "path": str(skill_path),
                "message": f"Skill '{safe_name}' created. Invoke it with: /skill {safe_name}"
                           + (f" (backtest-validated by strategy '{linked}')" if linked else "")
            }
        except Exception as e:
            log.error(f"Failed to write skill: {e}")
            return {"error": str(e)}

    elif name == "list_hermes_skills":
        try:
            if not HERMES_SKILLS_DIR.exists():
                return {"skills": [], "skills_dir": str(HERMES_SKILLS_DIR)}
            skills = []
            for f in sorted(HERMES_SKILLS_DIR.glob("*.md")):
                text = f.read_text(encoding="utf-8", errors="ignore")
                # Pull frontmatter description if present
                desc = ""
                if text.startswith("---"):
                    fm_end = text.find("---", 3)
                    if fm_end > 0:
                        fm = text[3:fm_end]
                        for line in fm.splitlines():
                            if line.strip().startswith("description:"):
                                desc = line.split(":", 1)[1].strip()
                skills.append({"name": f.stem, "file": f.name, "description": desc})
            return {"skills": skills, "count": len(skills), "skills_dir": str(HERMES_SKILLS_DIR)}
        except Exception as e:
            return {"error": str(e)}

    elif name == "delete_hermes_skill":
        skill_name = args.get("skill_name", "").strip()
        if not skill_name:
            return {"error": "'skill_name' is required"}
        safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in skill_name)
        path = HERMES_SKILLS_DIR / f"{safe_name}.md"
        if not path.exists():
            return {"success": False, "message": f"Skill not found: {path}"}
        path.unlink()
        log.info(f"Skill deleted: {path}")
        return {"success": True, "message": f"Skill '{safe_name}' deleted."}

    elif name == "get_hermes_config":
        return {
            "vault_path":          OBSIDIAN_VAULT_ROOT,
            "skills_dir":          str(HERMES_SKILLS_DIR),
            "hermes_home_dir":     str(HERMES_HOME_DIR),
            "log_dir":             str(LOG_DIR),
            "log_level":           LOG_LEVEL,
            "default_instrument":  DEFAULT_INSTRUMENT,
            "mtf_timeframes":      DEFAULT_MTF_LIST,
            "max_risk_pct":        DEFAULT_MAX_RISK_PCT,
            "max_daily_drawdown":  DEFAULT_MAX_DAILY_DD,
            "service_urls": {
                "mt5_bridge": MT5_URL, "paper_trader": PAPER_URL,
                "preprocessor": PREPROC_URL, "backtester": BACKTEST_URL,
                "mcp_bridge": MCP_URL
            },
            "note": "All values are set via environment variables. Edit .env or "
                    "scripts/start_mcp_server.ps1 and restart the MCP server to change them."
        }

    else:
        return {"error": f"Unknown tool: {name}"}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body   = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    def ok(result):
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})
    def err(code, msg):
        return JSONResponse({"jsonrpc": "2.0", "id": req_id,
                             "error": {"code": code, "message": msg}})

    if method == "initialize":
        return ok({"protocolVersion": "2024-11-05",
                   "serverInfo": {"name": "hermes-trading", "version": "1.0"},
                   "capabilities": {"tools": {}}})
    elif method == "tools/list":
        return ok({"tools": TOOLS})
    elif method == "tools/call":
        try:
            result = handle_tool(params.get("name",""), params.get("arguments",{}))
            return ok({"content": [{"type": "text",
                                     "text": json.dumps(result, indent=2, default=str)}]})
        except Exception as e:
            return err(-32603, str(e))
    elif method == "ping":
        return ok({})
    else:
        return err(-32601, f"Method not found: {method}")


@app.get("/health")
def health():
    return {"status": "ok", "server": "hermes-trading-mcp", "port": 7779}


if __name__ == "__main__":
    port = int(os.getenv("MCP_TRADING_PORT", "7779"))
    print(f"\nHermes Trading MCP Server on http://localhost:{port}/mcp")
    print("Add to ~/.hermes/config.yaml:")
    print("  mcp_servers:")
    print("    hermes_trading:")
    print(f"      url: http://localhost:{port}/mcp\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
