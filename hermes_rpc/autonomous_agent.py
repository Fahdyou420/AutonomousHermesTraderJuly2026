"""
Hermes Autonomous Trading Agent v2
====================================
Runs permanently on the Windows host.
Calls Ollama directly — no SSE parsing, no hermes_rpc proxy hop.
Calls Docker services directly for data.
Operates on wall-clock time — independent of MT5 ticks or market hours.

Cycle:
  Every 15 min : market scan + SMC analysis + trade monitor
  Every 4 hr   : hypothesis backtest + paper trade entry if approved
  Every 24 hr  : performance review + self-improvement + skill update
  On startup   : context load from vault, model discovery, state restore
"""

import os, sys, json, time, logging, requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AGENT] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("hermes_agent.log", encoding="utf-8")
    ]
)
log = logging.getLogger("hermes_agent")

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL     = os.getenv("OLLAMA_URL",        "http://localhost:11434")
MT5_URL        = os.getenv("MT5_BRIDGE_URL",    "http://localhost:5558")
PAPER_URL      = os.getenv("PAPER_TRADER_URL",  "http://localhost:5561")
BACKTEST_URL   = os.getenv("BACKTESTER_URL",    "http://localhost:5560")
MCP_URL        = os.getenv("MCP_BRIDGE_URL",    "http://localhost:5562")
VAULT_ROOT     = os.getenv("OBSIDIAN_VAULT_ROOT","C:\\Fahd data AI\\Fahd\\Vault")

INSTRUMENT     = os.getenv("HERMES_INSTRUMENT", "XAUUSD")
TIMEFRAME      = os.getenv("HERMES_TIMEFRAME",  "M15")
MAX_RISK_PCT   = float(os.getenv("MAX_RISK_PCT","1.0"))
MAX_DAILY_DD   = float(os.getenv("MAX_DAILY_DD","3.0"))
PAPER_MODE     = os.getenv("TRADING_MODE",      "paper")

SCAN_INTERVAL_MIN    = int(os.getenv("SCAN_INTERVAL_MIN",    "15"))
RESEARCH_INTERVAL_HR = int(os.getenv("RESEARCH_INTERVAL_HR", "4"))
REVIEW_INTERVAL_HR   = int(os.getenv("REVIEW_INTERVAL_HR",   "24"))

# ── State ─────────────────────────────────────────────────────────────────────
state = {
    "cycle":           0,
    "model":           None,
    "bias":            "NEUTRAL",
    "setups":          [],
    "daily_dd":        0.0,
    "last_scan":       datetime.utcnow() - timedelta(minutes=SCAN_INTERVAL_MIN + 1),
    "last_research":   datetime.utcnow() - timedelta(hours=RESEARCH_INTERVAL_HR + 1),
    "last_review":     datetime.utcnow() - timedelta(hours=REVIEW_INTERVAL_HR + 1),
    "running":         True,
}

# ── Ollama direct call ────────────────────────────────────────────────────────

def discover_model() -> str:
    """Pick best available Ollama model."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.ok:
            models = [m["name"] for m in r.json().get("models", [])]
            log.info(f"Ollama models available: {models}")
            for kw in ["hermes", "llama3.1", "llama3", "mistral", "qwen"]:
                for m in models:
                    if kw in m.lower():
                        log.info(f"Selected model: {m}")
                        return m
            if models:
                log.info(f"Fallback to first model: {models[0]}")
                return models[0]
    except Exception as e:
        log.error(f"Ollama model discovery failed: {e}")
    return "llama3.2"


def ask(prompt: str, system: str = None, timeout: int = 180) -> str:
    """
    Call Ollama directly. Returns the full response text.
    No streaming — simpler, more reliable for an automated agent.
    """
    model = state["model"] or "llama3.2"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=timeout
        )
        if r.status_code == 200:
            return r.json().get("message", {}).get("content", "").strip()
        log.error(f"Ollama {r.status_code}: {r.text[:300]}")
    except requests.exceptions.Timeout:
        log.error(f"Ollama timed out after {timeout}s")
    except Exception as e:
        log.error(f"Ollama call failed: {e}")
    return ""


# ── Data helpers ──────────────────────────────────────────────────────────────

def get(url: str, timeout: int = 5) -> Optional[Any]:
    try:
        r = requests.get(url, timeout=timeout)
        return r.json() if r.ok else None
    except Exception:
        return None


def post(url: str, payload: dict, timeout: int = 30) -> Optional[Any]:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r.json() if r.ok else None
    except Exception:
        return None


def get_bars(instrument: str = None, tf: str = None, n: int = 200) -> List[Dict]:
    """Get OHLCV bars. Tries MT5 bridge first, falls back to yfinance."""
    instr = instrument or INSTRUMENT
    timeframe = tf or TIMEFRAME

    # Try MT5 bridge
    data = get(f"{MT5_URL}/latest_bars?instrument={instr}&tf={timeframe}&n={n}", timeout=5)
    if data and isinstance(data, list) and len(data) > 0:
        log.debug(f"Got {len(data)} bars from MT5 bridge")
        return data

    # Fallback: yfinance (works on weekends, great for BTC)
    log.info(f"MT5 bridge has no data for {instr}. Trying yfinance fallback...")
    try:
        import yfinance as yf
        # Map instrument to Yahoo ticker
        ticker_map = {
            "XAUUSD": "GC=F", "BTCUSD": "BTC-USD", "EURUSD": "EURUSD=X",
            "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "BTCUSDT": "BTC-USD"
        }
        tf_map = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
                  "H1": "60m", "H4": "1h", "D1": "1d", "W1": "1wk"}
        ticker  = ticker_map.get(instr.upper(), instr)
        yf_tf   = tf_map.get(timeframe.upper(), "15m")
        period  = "5d" if yf_tf in ["1m","5m","15m","30m"] else "60d"

        df = yf.download(ticker, period=period, interval=yf_tf,
                         progress=False, auto_adjust=True)
        if df.empty:
            log.warning(f"yfinance returned no data for {ticker}")
            return []

        bars = []
        for ts, row in df.tail(n).iterrows():
            bars.append({
                "timestamp": int(ts.timestamp()),
                "instrument": instr,
                "timeframe": timeframe,
                "open":  float(row["Open"]),
                "high":  float(row["High"]),
                "low":   float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row.get("Volume", 0)),
                "source": "yfinance"
            })
        log.info(f"yfinance: got {len(bars)} bars for {ticker}")
        return bars
    except ImportError:
        log.warning("yfinance not installed. Run: pip install yfinance")
    except Exception as e:
        log.error(f"yfinance fallback failed: {e}")
    return []


def format_bars_for_prompt(bars: List[Dict], n: int = 50) -> str:
    """Format last N bars as compact text for the LLM prompt."""
    if not bars:
        return "No bar data available."
    recent = bars[-n:]
    lines = ["timestamp,open,high,low,close,volume"]
    for b in recent:
        ts = datetime.utcfromtimestamp(b.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M")
        lines.append(f"{ts},{b.get('open',0):.2f},{b.get('high',0):.2f},"
                     f"{b.get('low',0):.2f},{b.get('close',0):.2f},{b.get('volume',0)}")
    return "\n".join(lines)


def write_vault(rel_path: str, content: str, frontmatter: dict = None):
    """Write a markdown note directly to the Obsidian vault on disk."""
    try:
        fm_lines = ["---"]
        fm_lines.append(f"instrument: {INSTRUMENT}")
        fm_lines.append(f"timestamp: {now_str()}")
        fm_lines.append(f"agent_cycle: {state['cycle']}")
        if frontmatter:
            for k, v in frontmatter.items():
                fm_lines.append(f"{k}: {v}")
        fm_lines.append("---")
        fm_lines.append("")
        full = "\n".join(fm_lines) + content

        path = Path(VAULT_ROOT) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(full, encoding="utf-8")
        log.info(f"Vault note written: {rel_path}")
    except Exception as e:
        log.error(f"Vault write failed ({rel_path}): {e}")


def now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def date_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")

def is_market_open() -> bool:
    now = datetime.utcnow()
    wd = now.weekday()
    if wd == 5: return False
    if wd == 4 and now.hour >= 22: return False
    if wd == 6 and now.hour < 22: return False
    return True


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM = """You are Hermes, an autonomous AI trading agent specializing in SMC/ICT methodology for XAUUSD and crypto.

Your core competencies:
- Smart Money Concepts: BOS, CHoCH, Order Blocks, FVGs, Liquidity sweeps
- ICT concepts: Killzones, PD Arrays, displacement, mitigation
- Risk management: max 1% per trade, staged progression (hypothesis->backtest->paper->live)
- Multi-timeframe analysis: HTF bias, LTF entry

When you identify setups, be precise: exact price levels, not ranges.
When you are uncertain, say so and reduce confidence rating.
Always consider DXY correlation for Gold analysis.
You are running autonomously. Be decisive. Write clear structured markdown in your responses."""


# ── Agent cycles ──────────────────────────────────────────────────────────────

def run_market_scan():
    log.info(f"[SCAN #{state['cycle']}] Fetching bars for {INSTRUMENT} {TIMEFRAME}...")
    bars = get_bars(n=300)

    if not bars:
        log.warning("[SCAN] No bar data available from any source.")
        return

    bar_table = format_bars_for_prompt(bars, n=100)
    current_price = bars[-1].get("close", 0) if bars else 0
    market_status = "OPEN" if is_market_open() else "CLOSED (weekend - structural analysis only)"

    prompt = f"""Current time: {now_str()}
Market: {market_status}
Instrument: {INSTRUMENT} | Timeframe: {TIMEFRAME}
Current price: {current_price:.2f}
Previous bias: {state['bias']}

OHLCV data (last 100 bars, newest last):
{bar_table}

Perform a full SMC/ICT analysis:

## 1. Market Structure
- Identify the last 3 significant swing highs and lows with prices
- BOS (Break of Structure): last confirmed break, price and direction
- CHoCH (Change of Character): any recent shifts
- Overall HTF bias: BULLISH / BEARISH / RANGING

## 2. Key Levels
- Bearish Order Blocks: price zones, strength rating (1-5)
- Bullish Order Blocks: price zones, strength rating (1-5)
- Unmitigated FVGs: price range, direction, age (bars old)
- Liquidity pools: equal highs/lows worth targeting

## 3. Current Context
- Which session is active or most recently closed
- Is price inside a PD array (OB, FVG, premium/discount zone)?
- Any displacement candles in last 10 bars?

## 4. Bias
State: BULLISH / BEARISH / NEUTRAL
Confidence: HIGH / MEDIUM / LOW
Reason: one clear sentence

## 5. Setups (if any)
For each HIGH or MEDIUM confidence setup:
- Setup: [type]
- Direction: BUY/SELL
- Entry zone: [price range]
- Stop loss: [exact price]
- Take profit: [exact price]
- R:R: [ratio]
- Confidence: HIGH/MEDIUM/LOW
- Trigger: what needs to happen before entry

If market is closed: analyse structure only, no entry setups needed."""

    response = ask(prompt, system=SYSTEM, timeout=240)
    if not response:
        log.warning("[SCAN] No response from model.")
        return

    # Extract bias
    for line in response.upper().split("\n"):
        if "BULLISH" in line and "BIAS" in line:
            state["bias"] = "BULLISH"; break
        elif "BEARISH" in line and "BIAS" in line:
            state["bias"] = "BEARISH"; break
        elif "NEUTRAL" in line and "BIAS" in line:
            state["bias"] = "NEUTRAL"; break

    log.info(f"[SCAN] Bias: {state['bias']} | Price: {current_price:.2f}")

    # Queue HIGH confidence setups for backtesting
    if "CONFIDENCE: HIGH" in response.upper() or "HIGH CONFIDENCE" in response.upper():
        state["setups"].append({
            "ts": now_str(),
            "price": current_price,
            "bias": state["bias"],
            "analysis": response,
            "cycle": state["cycle"],
            "bars_snapshot": bars[-20:]
        })
        log.info(f"[SCAN] High-confidence setup queued ({len(state['setups'])} pending)")

    write_vault(
        f"01_MARKET_STUDIES/{date_str()}_scan_{state['cycle']:04d}.md",
        response,
        {"type": "market_scan", "bias": state["bias"], "price": current_price}
    )

    state["last_scan"] = datetime.utcnow()
    state["cycle"] += 1


def run_trade_monitor():
    """Check open positions, manage risk, trail stops if profitable."""
    positions = get(f"{PAPER_URL}/positions") or []
    stats     = get(f"{PAPER_URL}/stats")     or {}

    dd = float(stats.get("max_drawdown_percent", 0.0))
    state["daily_dd"] = dd

    if dd >= MAX_DAILY_DD:
        log.warning(f"[MONITOR] Daily DD {dd:.1f}% >= limit {MAX_DAILY_DD}%. Clearing setup queue.")
        state["setups"].clear()
        return

    if not positions:
        log.info("[MONITOR] No open positions.")
        return

    bars  = get_bars(n=10) or []
    price = bars[-1]["close"] if bars else 0

    prompt = f"""Current time: {now_str()}
Current {INSTRUMENT} price: {price:.2f}
Current bias: {state['bias']}
Daily drawdown: {dd:.2f}% (limit: {MAX_DAILY_DD}%)

Open paper positions:
{json.dumps(positions, indent=2)}

For each position, assess:
1. Is it in profit? If profit > 1R, should we trail SL to breakeven?
2. Has bias reversed against this trade? Flag for early close if so.
3. Is it beyond 48 hours with no progress? Flag for review.
4. Has price hit SL or TP?

Output your assessment as JSON:
{{
  "actions": [
    {{"ticket": 123, "action": "NONE|TRAIL_BE|CLOSE|MONITOR", "reason": "..."}},
  ],
  "overall": "ALL_CLEAR|ATTENTION_NEEDED"
}}

Only output JSON, no other text."""

    response = ask(prompt, system=SYSTEM, timeout=60)
    if not response:
        return

    try:
        # Extract JSON from response
        start = response.find("{")
        end   = response.rfind("}") + 1
        if start >= 0 and end > start:
            data    = json.loads(response[start:end])
            actions = data.get("actions", [])
            for action in actions:
                if action.get("action") == "TRAIL_BE":
                    log.info(f"[MONITOR] Trail to BE: ticket {action['ticket']} — {action['reason']}")
                elif action.get("action") == "CLOSE":
                    log.info(f"[MONITOR] Flagging close: ticket {action['ticket']} — {action['reason']}")
                    post(f"{PAPER_URL}/close/{action['ticket']}", {})
            overall = data.get("overall", "")
            log.info(f"[MONITOR] Status: {overall} | {len(positions)} positions | DD: {dd:.2f}%")
    except json.JSONDecodeError:
        log.warning(f"[MONITOR] Could not parse JSON response: {response[:200]}")


def run_hypothesis_and_backtest():
    """Take the best queued setup, backtest it, paper trade if it passes."""
    if not state["setups"]:
        log.info("[RESEARCH] No setups queued.")
        return

    setup = state["setups"].pop(0)
    log.info(f"[RESEARCH] Testing setup from cycle {setup['cycle']}...")

    bars  = get_bars(n=500) or []
    price = bars[-1]["close"] if bars else setup["price"]

    prompt = f"""You are performing hypothesis testing on a trading setup.

Setup identified at cycle {setup['cycle']}:
Price at time of signal: {setup['price']:.2f}
Current price: {price:.2f}
Bias at time: {setup['bias']}

Original analysis:
{setup['analysis'][:1500]}

Historical bar data for backtesting context (last 500 bars available):
{format_bars_for_prompt(bars, n=50)}

HYPOTHESIS TEST:
1. Identify the specific entry type from the analysis (OB entry / FVG fill / liquidity sweep / CHoCH confirmation)
2. Scan the bar data: how many times did this pattern appear in the last 500 bars?
3. For each occurrence, what was the outcome? (estimate from price action)
4. Calculate estimated statistics:
   - Occurrences found: N
   - Estimated wins (price moved in direction): W
   - Estimated win rate: W/N %
   - Estimated avg R:R based on typical SL/TP levels for this pattern
   - Estimated profit factor

5. VERDICT:
   - APPROVED if: win rate > 52% AND estimated profit factor > 1.3
   - REJECTED if below either threshold
   - INSUFFICIENT_DATA if fewer than 10 occurrences found

State VERDICT: APPROVED or VERDICT: REJECTED or VERDICT: INSUFFICIENT_DATA

6. If APPROVED, specify exact entry parameters for current market:
   - Direction: BUY/SELL
   - Entry: [price]
   - SL: [price]
   - TP: [price]
   - Lots for 1% risk on $10,000 account at current price
   - Note if price is still within entry zone or has moved away (PRICE_MOVED_AWAY)"""

    response = ask(prompt, system=SYSTEM, timeout=300)
    if not response:
        log.warning("[RESEARCH] No response.")
        return

    write_vault(
        f"05_RND/results/{date_str()}_hypothesis_{setup['cycle']:04d}.md",
        response,
        {"type": "hypothesis", "bias": setup["bias"], "source_cycle": setup["cycle"]}
    )

    if "VERDICT: APPROVED" in response:
        log.info("[RESEARCH] Hypothesis APPROVED. Generating paper trade signal.")
        run_paper_entry(setup, response, price)
    elif "VERDICT: INSUFFICIENT_DATA" in response:
        log.info("[RESEARCH] Insufficient data. Re-queuing for next cycle.")
        state["setups"].append(setup)  # try again later with more data
    else:
        log.info("[RESEARCH] Hypothesis REJECTED.")

    state["last_research"] = datetime.utcnow()


def run_paper_entry(setup: dict, research: str, current_price: float):
    """Send a real paper trade signal after a hypothesis passes."""
    if "PRICE_MOVED_AWAY" in research:
        log.info("[PAPER] Price moved away from entry zone. Skipping signal.")
        return

    prompt = f"""Extract the exact trade parameters from this approved hypothesis report and output ONLY valid JSON.

Research report:
{research[:2000]}

Current price: {current_price:.2f}
Instrument: {INSTRUMENT}

Output exactly this JSON structure, no other text:
{{
  "instrument": "{INSTRUMENT}",
  "direction": "BUY or SELL",
  "entry_price": 0.00,
  "sl": 0.00,
  "tp": 0.00,
  "lots": 0.01,
  "mode": "{PAPER_MODE}",
  "strategy_id": "hermes_auto_{state['cycle']}",
  "setup_type": "describe setup type",
  "agent_notes": "one sentence why this trade qualifies"
}}"""

    response = ask(prompt, system=SYSTEM, timeout=60)
    if not response:
        return

    try:
        start = response.find("{")
        end   = response.rfind("}") + 1
        if start < 0 or end <= start:
            log.error(f"[PAPER] No JSON in response: {response[:200]}")
            return

        signal = json.loads(response[start:end])

        # Validate minimum fields
        required = ["direction", "entry_price", "sl", "tp", "lots"]
        if not all(signal.get(f) for f in required):
            log.error(f"[PAPER] Signal missing required fields: {signal}")
            return

        # Safety checks
        if signal.get("lots", 0) > 1.0:
            signal["lots"] = 0.01  # cap lot size
        if signal.get("direction") not in ("BUY", "SELL"):
            log.error(f"[PAPER] Invalid direction: {signal.get('direction')}")
            return

        # Add required fields
        signal.update({
            "signal_id":  f"auto_{state['cycle']}_{int(time.time())}",
            "timestamp":  int(time.time()),
            "timeframe":  TIMEFRAME,
            "session":    "auto",
            "confidence": "high",
            "status":     "pending"
        })

        result = post(f"{MCP_URL}/signal", signal, timeout=15)
        if result:
            log.info(f"[PAPER] Signal sent: {signal['direction']} {signal.get('lots')} lots @ {signal.get('entry_price')}")
            write_vault(
                f"03_TRADE_JOURNAL/paper/{date_str()}_trade_{state['cycle']:04d}.md",
                f"## Paper Trade Signal\n\n```json\n{json.dumps(signal, indent=2)}\n```\n\n## Research Basis\n\n{research[:800]}",
                {"type": "paper_trade", "direction": signal["direction"]}
            )
        else:
            log.warning("[PAPER] Signal POST returned no response.")

    except json.JSONDecodeError as e:
        log.error(f"[PAPER] JSON parse error: {e} | Response: {response[:300]}")
    except Exception as e:
        log.error(f"[PAPER] Signal error: {e}")


def run_performance_review():
    """Daily self-review: analyse trades, update rules, prep next session."""
    log.info("[REVIEW] Running daily performance review...")

    stats   = get(f"{PAPER_URL}/stats")      or {}
    history = get(f"{PAPER_URL}/history?n=50") or []

    # Load existing agent rules from vault
    rules_path = Path(VAULT_ROOT) / "04_KNOWLEDGE_BASE" / "agent_rules.md"
    existing_rules = rules_path.read_text(encoding="utf-8") if rules_path.exists() else "No rules yet."

    prompt = f"""Daily self-review for {date_str()}.

Trading statistics today:
{json.dumps(stats, indent=2)}

Last 50 closed trades:
{json.dumps(history[:20], indent=2)}

Current agent rules:
{existing_rules[:1000]}

SELF-REVIEW TASKS:

## 1. Performance Analysis
- Win rate, profit factor, average R:R today
- Best performing setup types
- Worst performing setup types
- Best and worst sessions (Asian/London/NY)

## 2. Mistake Identification
- What caused each losing trade? Be specific.
- Were any entries taken outside of high-probability conditions?
- Were stops placed correctly or too tight/wide?

## 3. Updated Rules
Based on today's results, write 3-5 updated trading rules.
Format each as: RULE: [condition] -> [action]
Example: RULE: Spread > 30 pips -> Skip entry, wait for spread compression

## 4. Tomorrow's Preparation
- Key price levels to monitor for {INSTRUMENT}
- Expected bias for next session based on today's structure
- Any high-impact news or events to be aware of

## 5. Model Self-Assessment
Rate your autonomous decision quality today: 1-10
What would you do differently?"""

    response = ask(prompt, system=SYSTEM, timeout=300)
    if not response:
        log.warning("[REVIEW] No response.")
        return

    # Update agent rules file
    if "RULE:" in response:
        rules_lines = [l for l in response.split("\n") if l.strip().startswith("RULE:")]
        if rules_lines:
            updated = f"# Agent Rules — Updated {date_str()}\n\n"
            updated += "\n".join(rules_lines)
            rules_path.parent.mkdir(parents=True, exist_ok=True)
            rules_path.write_text(updated, encoding="utf-8")
            log.info(f"[REVIEW] Agent rules updated: {len(rules_lines)} rules")

    write_vault(
        f"03_TRADE_JOURNAL/reviews/{date_str()}_daily_review.md",
        response,
        {
            "type": "daily_review",
            "win_rate": stats.get("win_rate", 0),
            "profit_factor": stats.get("profit_factor", 0)
        }
    )

    log.info("[REVIEW] Daily review complete.")
    state["last_review"] = datetime.utcnow()


def run_startup():
    """Load context from vault on startup."""
    log.info("[INIT] Loading context from vault...")

    rules_path = Path(VAULT_ROOT) / "04_KNOWLEDGE_BASE" / "agent_rules.md"
    rules = rules_path.read_text(encoding="utf-8") if rules_path.exists() else "No existing rules."

    bars  = get_bars(n=50) or []
    price = bars[-1]["close"] if bars else 0
    bar_summary = format_bars_for_prompt(bars, n=20)

    prompt = f"""Agent starting new session at {now_str()}.
Current {INSTRUMENT} price: {price:.2f}
Market: {'OPEN' if is_market_open() else 'CLOSED (weekend)'}

Existing agent rules:
{rules[:500]}

Recent price action:
{bar_summary}

Provide:
1. Quick structural read (2-3 sentences) — what is price doing right now?
2. Starting bias for this session
3. Key levels to watch (2-3 levels with prices)
4. Any notable patterns in the last 20 bars

Keep it brief — this is a startup check, not a full scan."""

    response = ask(prompt, system=SYSTEM, timeout=120)
    if response:
        log.info(f"[INIT] Startup context:\n{response[:400]}")
        # Extract bias
        for line in response.upper().split("\n"):
            if "BULLISH" in line:
                state["bias"] = "BULLISH"; break
            elif "BEARISH" in line:
                state["bias"] = "BEARISH"; break
        write_vault(
            f"03_TRADE_JOURNAL/sessions/{date_str()}_session_start.md",
            response,
            {"type": "session_start", "starting_price": price}
        )
    log.info(f"[INIT] Starting bias: {state['bias']}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def wait_for_ollama(max_wait: int = 120) -> bool:
    log.info(f"Waiting for Ollama at {OLLAMA_URL}...")
    for i in range(max_wait):
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            if r.ok:
                models = [m["name"] for m in r.json().get("models", [])]
                log.info(f"Ollama ready. Models: {models}")
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    log.info("=" * 60)
    log.info("  HERMES AUTONOMOUS AGENT v2")
    log.info(f"  Instrument : {INSTRUMENT} {TIMEFRAME}")
    log.info(f"  Mode       : {PAPER_MODE} | Risk: {MAX_RISK_PCT}% | DD halt: {MAX_DAILY_DD}%")
    log.info(f"  Scan: {SCAN_INTERVAL_MIN}min | Research: {RESEARCH_INTERVAL_HR}hr | Review: {REVIEW_INTERVAL_HR}hr")
    log.info("=" * 60)

    if not wait_for_ollama():
        log.error("Ollama unreachable. Is it running? Run: ollama serve")
        sys.exit(1)

    state["model"] = discover_model()
    log.info(f"Using model: {state['model']}")

    # Install yfinance if not present (weekend data fallback)
    try:
        import yfinance
    except ImportError:
        log.info("Installing yfinance for weekend data fallback...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "yfinance", "-q"], check=False)

    run_startup()

    log.info("Autonomous loop started. Ctrl+C to stop.")

    while state["running"]:
        now = datetime.utcnow()
        try:
            # 15-min scan + monitor
            if (now - state["last_scan"]).total_seconds() >= SCAN_INTERVAL_MIN * 60:
                run_market_scan()
                run_trade_monitor()

            # 4-hour research
            if (now - state["last_research"]).total_seconds() >= RESEARCH_INTERVAL_HR * 3600:
                run_hypothesis_and_backtest()

            # 24-hour review
            if (now - state["last_review"]).total_seconds() >= REVIEW_INTERVAL_HR * 3600:
                run_performance_review()

        except KeyboardInterrupt:
            log.info("Interrupted. Shutting down.")
            state["running"] = False
            break
        except Exception as e:
            log.error(f"Main loop error: {e}", exc_info=True)

        time.sleep(30)

    log.info("Agent stopped.")


if __name__ == "__main__":
    main()
