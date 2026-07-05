# BTCUSD Retest — How the System Actually Worked

## The Full System (what exists)

```
YOU / Hermes Agent
       |
       v
+-------------------+     JSON/HTTP      +------------------+
| Hermes MCP Server | -----------------> |  MT5 Bridge      |
|  (localhost:7779) |                    |  (localhost:5558)|
+-------------------+                    +------------------+
       |                                        |
       | uses yfinance                         | talks to MetaTrader 5 EA via ZMQ
       v                                        v
+-------------------+                    +------------------+
| Preprocessor      |                    |  MT5 / EA        |
|  (localhost:5559) |                    |  (trading terminal) |
+-------------------+                    +------------------+
       |                                        |
       | computes SMC                           | sends orders / prices
       v                                        v
+-------------------+                    +------------------+
| Backtester        |                    |  Execution       |
|  (localhost:5560) |                    |  (localhost:5563)|
+-------------------+                    +------------------+
       |                                        |
       | runs strategies                        | sends orders to broker
       v                                        v
+-------------------+                    +------------------+
| Paper Trader      | ------------------> |  Broker/MT5      |
|  (localhost:5561) |   paper positions    |                  |
+-------------------+                      +------------------+
       |
       | writes trade history
       v
+-------------------+
| SQLite / Files     |
+-------------------+

Dashboard containers (8080 / 3000)  ->  web UI, not used in retest
MCP Bridge (5562)                   ->  protocol bridge, not used
Ollama / Embedder / Redis / Chroma  ->  AI memory/search, not used
```

---

## What I Actually Used (and what I skipped)

### Layer 1 — Entry Point
**Used:** `Hermes MCP Server` (`localhost:7779`)
- The retest script sent JSON-RPC calls here.
- Think of this as the receptionist. It receives requests and forwards them.

**Why:** Everything the script needed was already exposed through this server. No need to call lower layers directly.

---

### Layer 2 — Market Data
**Used:** `yfinance` inside `hermes_mcp_server.py`
- Downloaded BTCUSD M15 bars directly from Yahoo Finance.
- Filled missing volume values with `0` to avoid crashes.

**Did NOT use:** 
- `MT5 Bridge` (`localhost:5558`) — the `/latest_bars` endpoint timed out.
- `Preprocessor` (`localhost:5559`) — not needed because MCP server already had yfinance fallback.

**Why:** The MT5 EA was not connected (no heartbeat), so live MT5 bars were unavailable. yfinance was the reliable fallback already built into the MCP server.

---

### Layer 3 — SMC Analysis
**Used:** `Preprocessor` (`localhost:5559`) via MCP tool `get_smc_analysis`
- Computed Fair Value Gaps (FVGs), Order Blocks (OBs), BOS, CHoCH.
- Returned JSON with IDs and geometry for chart drawing.

**Why:** SMC logic lives in the preprocessor. The MCP server calls it internally when requested.

---

### Layer 4 — Backtesting
**Used:** `Backtester` (`localhost:5560`) via MCP tool `run_full_backtest`
- Ran three strategies: `smc_ob_entry`, `smc_fvg_fill`, `smc_liquidity_sweep`.
- Fixed strategy aliases so the names the MCP layer expects map to actual engine classes.
- Populated `/data/market_data` in the backtester container with BTCUSD bars so the engine had data to simulate on.

**Did NOT use:** `Execution` service
- We only simulated trades, no real orders.

**Why:** Backtesting validates strategy ideas before any paper or live trading. It uses historical bars and a simulated broker.

---

### Layer 5 — Paper Trading
**Used:** `Paper Trader` (`localhost:5561`) via MCP tools:
- `send_paper_trade` — created a BUY position
- `get_positions` / `get_trade_history` — verified it appeared and later closed
- `close_position` — closed it manually

**Fixed:** The `close_position` ticket parameter was a string ID (`mcp_...`), not an integer. Patched the retest script to pass it as text.

**Why:** Paper trading is the safety net. It proves the signal → position → close lifecycle works without risking real money.

---

### Layer 6 — Chart Annotations
**Used:** `draw_on_chart` and `visualise_analysis`
- Drew horizontal lines at test prices.
- Cleared and redrew 54 SMC objects (FVGs, OBs, BOS, CHoCH) on the chart.

**Why:** Visual confirmation that SMC levels exist and are drawable in the current chart session.

---

### Layer 7 — Config / plumbing
**Used:** `.agent-config.json` created with `default_instrument: BTCUSD`.
**Fixed:** Host-side `hermes_mcp_server.py` defaults are localhost URLs, so when I launched it manually on Windows it actually called `localhost:5559/5560/5561` instead of Docker internal hostnames like `preprocessor:5559`.

**Why Docker internal hostnames failed when running the MCP server manually:**  
The MCP server runs on the host. It cannot resolve Docker DNS names like `preprocessor` or `backtester` unless it runs inside Docker network. By using localhost URLs, it goes through the published ports and works from the host.

---

## What I Did NOT Touch and Why

| Component | Status | Why skipped |
|-----------|--------|-------------|
| Dashboard (8080/3000) | running | Not needed for retest; retest uses MCP JSON-RPC, not UI |
| MCP Bridge (5562) | running | retest script talks directly to Hermes MCP Server |
| Execution (5563) | running | Paper trading path used; execution only for live orders |
| Ollama / Embedder / Redis / Chroma | running | AI memory/search not in retest scope |
| MT5 EA / ZMQ (5555-5557) | disconnected | EA not running; yfinance was sufficient |

---

## The Actual Data Flow (simplified)

```
Retest Script
    |
    | JSON-RPC
    v
Hermes MCP Server :7779
    |
    |-- yfinance ----------------> BTCUSD bars
    |
    |-- HTTP :5559 --------------> Preprocessor computes SMC
    |
    |-- HTTP :5560 --------------> Backtester runs strategy aliases
    |       uses /data/market_data/BTCUSD_M15_yfinance.json
    |
    |-- HTTP :5561 --------------> Paper Trader sends/closes positions
    |
    |-- MT5 Bridge :5558 (optional, timed out)
```

---

## Bottom Line

I used the **MCP server as the single entry point** and called 4 downstream services through it:
1. yfinance for bars
2. preprocessor for SMC
3. backtester for strategy simulation
4. paper trader for position lifecycle

I skipped the dashboard, execution, MCP bridge, and AI memory layers because the retest scope was: **data → analysis → backtest → paper trade → chart draw**.

The fixes were:
- yfinance NaN volume coercion
- strategy alias mapping in the backtester
- copying BTCUSD JSON data into the backtester container
- changing `close_position` ticket from `int` to `str`
- making sure host-side MCP server calls `localhost`, not Docker DNS names
