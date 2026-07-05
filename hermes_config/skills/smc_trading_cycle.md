---
name: smc_trading_cycle
description: Full autonomous SMC/ICT trading cycle with MT5 chart visualisation, custom indicators, and backtesting
version: "2.0"
author: Hermes Trading Agent
tags: [trading, smc, ict, xauusd, btcusd, autonomous, visualisation]
---

# SMC Trading Cycle Skill v2.0

## Usage
Call with one phase: `scan`, `monitor`, `research`, `review`, `status`, `draw`

---

## Phase: scan

The core 15-minute autonomous loop. Always visualises results on the MT5 chart.

1. Call `mcp_hermes_trading_get_system_status`
   - Note EA connected status. If disconnected, data comes from yfinance automatically.

2. Call `mcp_hermes_trading_get_market_bars` for XAUUSD M15, n=300
   - Also call for BTCUSD H1, n=200 (BTC trades 24/7, always analyse it)

3. Perform full SMC/ICT analysis on each instrument:
   - **Market structure**: identify last 3 swing highs/lows with exact prices
   - **BOS**: last confirmed break, direction, price level
   - **CHoCH**: any recent character changes that shift bias
   - **Order Blocks**: unmitigated bullish OBs (last bearish candle before bullish BOS) and bearish OBs
   - **FVGs**: open 3-candle imbalances, note size and age
   - **Liquidity**: equal highs/lows, stop hunt zones, inducement levels
   - **Session**: which killzone is active or approaching
   - **DXY correlation** for XAUUSD: if DXY bullish, lean bearish on Gold

4. Call `mcp_hermes_trading_visualise_analysis` with:
   - instrument, timeframe, n=300
   - clear_first=true
   - bias=your determined bias (BULLISH/BEARISH/NEUTRAL)
   This paints FVGs, OBs, BOS/CHoCH, liquidity ALL at once on the MT5 chart.

5. Determine bias per instrument with confidence level (HIGH/MEDIUM/LOW)

6. Identify any HIGH or MEDIUM confidence setups. For each:
   - Setup type: OB entry / FVG fill / liquidity sweep / CHoCH confirmation
   - Direction: BUY or SELL
   - Entry zone: exact price range
   - Stop loss: exact price (below/above structure, not arbitrary pips)
   - Take profit: next liquidity or FVG, minimum 2:1 R:R
   - Trigger: what must happen before entry (confirmation candle, session open, etc.)
   - Invalidation: what would cancel this setup

7. Write scan note to memory with: timestamp, bias, key levels, any setups found

8. If HIGH confidence setup exists: immediately run `research` phase for it

---

## Phase: monitor

Run alongside every scan to manage open positions.

1. Call `mcp_hermes_trading_get_open_positions`
2. Call `mcp_hermes_trading_get_trading_stats` — check daily drawdown
3. If daily drawdown >= 3%: stop new entries, log warning, do not run research phase
4. If no open positions: log "no positions to monitor" and return

5. For each open position:
   a. Get current price via `mcp_hermes_trading_get_market_bars` n=5
   b. Calculate current R = (current_price - entry) / (entry - sl) for BUY
   c. Actions based on R:
      - R >= 1.0: call `mcp_hermes_trading_send_paper_trade` with MODIFY to move SL to breakeven
      - R >= 2.0: consider trailing stop or partial close
      - R < 0 and bias reversed: flag for early close, call close_position
      - Position age > 48h with R < 0.3: evaluate if thesis still valid
   d. Update the chart: call `mcp_hermes_trading_draw_trade_signal` to refresh the visual

6. Write monitor note to memory

---

## Phase: research

Backtest a queued setup before committing capital.

1. Identify the setup from the last scan (from memory)

2. Call `mcp_hermes_trading_run_full_backtest` with:
   - instrument, timeframe from the setup
   - strategy_type: match the setup type (smc_ob_entry / smc_fvg_fill / smc_liquidity_sweep)
   - entry_logic: describe the exact conditions in natural language
   - lookback_bars: 1000 (more data = more reliable stats)
   - session_filter: the sessions where this setup type works best

3. Read the verdict in the response:
   - APPROVED (win rate > 52% AND profit factor > 1.3): proceed to paper trade
   - REJECTED: write rejection note to memory, discard setup, wait for next scan
   - If backtester offline: use the last 500 bars from get_market_bars and manually
     estimate the pattern frequency yourself

4. If APPROVED:
   a. Check current price is still within the entry zone
   b. Call `mcp_hermes_trading_send_paper_trade` with exact parameters
   c. If signal accepted: immediately call `mcp_hermes_trading_draw_trade_signal`
      to paint the entry arrow, SL line, and TP line on the MT5 chart
   d. Write trade note to memory including the backtest verdict

5. Write full hypothesis report to memory regardless of outcome

---

## Phase: review (run daily at 22:00 UTC after NY close)

Self-improvement loop. Hermes gets better every day.

1. Call `mcp_hermes_trading_get_trading_stats`
2. Call `mcp_hermes_trading_get_trade_history` n=50
3. Analyse:
   - Win rate, profit factor, average R:R for the period
   - Which setup types won most (OB entry vs FVG fill vs sweep)
   - Which sessions had best results (London vs NY vs overlap)
   - Recurring patterns in losing trades (too early, wrong session, counter-trend)
   - Average holding time of winners vs losers

4. Update your trading rules in memory. Format each rule as:
   `RULE: [condition] → [action]`
   Examples:
   - `RULE: Asian session + no London continuation → skip entry`
   - `RULE: FVG older than 20 bars → reduce confidence to LOW`
   - `RULE: Spread > 25 pips → no entry regardless of setup`

5. Draw performance summary on chart using `mcp_hermes_trading_draw_on_chart`:
   - A text label with today's win rate and profit factor in top-right corner

6. Write daily review note to memory

---

## Phase: draw

Manual chart refresh — call this anytime to repaint all structures.

1. Call `mcp_hermes_trading_visualise_analysis` with current instrument and timeframe
2. Call `mcp_hermes_trading_get_open_positions`
3. For each open position: call `mcp_hermes_trading_draw_trade_signal`
4. Report: "Chart updated — N FVGs, M OBs, K liquidity levels drawn"

---

## Phase: status

Quick health and portfolio check.

1. Call `mcp_hermes_trading_get_system_status`
2. Call `mcp_hermes_trading_get_open_positions`
3. Call `mcp_hermes_trading_get_trading_stats`
4. Call `mcp_hermes_trading_get_account_state`
5. Report in a clean table:
   - Services: online/offline for each
   - EA connected: yes/no
   - Open positions: count, total P&L
   - Account equity
   - Win rate and profit factor
   - Daily drawdown used / remaining

---

## Chart Drawing Reference

After every scan, the chart should show:
- **Blue boxes**: bullish FVGs (price imbalances to the upside)
- **Orange boxes**: bearish FVGs (price imbalances to the downside)
- **Green boxes**: bullish Order Blocks (institutional buying zones)
- **Red boxes**: bearish Order Blocks (institutional selling zones)
- **Yellow dashed lines**: BOS (Break of Structure)
- **Cyan dashed lines**: CHoCH (Change of Character)
- **Purple dots**: BSL/SSL (Buy-side / Sell-side Liquidity)
- **Green up arrows**: BUY entries
- **Red down arrows**: SELL entries
- **Red dotted lines**: Stop Loss levels
- **Green dotted lines**: Take Profit levels
- **Corner label**: Current bias (BULLISH = green, BEARISH = red, NEUTRAL = gray)

## Autonomous Schedule (set in Hermes cron)

```
*/15 * * * *   Use the smc_trading_cycle skill, phase: scan. Then phase: monitor.
0 */4 * * *    Use the smc_trading_cycle skill, phase: research.
0 22 * * *     Use the smc_trading_cycle skill, phase: review.
```

## Notes

- `visualise_analysis` fetches fresh SMC analysis AND draws everything in one call
- `run_full_backtest` fetches fresh bars (yfinance on weekends) then runs Python engine
- After every paper trade: always call `draw_trade_signal` so it appears on the chart
- The HermesStructure and HermesSignals indicators in MT5 (installed separately) 
  also paint these objects directly and work even without the agent running
- Minimum 2:1 R:R enforced before any trade signal
- 1% max risk enforced by the risk gatekeeper in send_paper_trade

---

## Strategy Development (run anytime)

### Creating a New Strategy

1. Call `mcp_hermes_trading_list_strategies` to see what already exists
2. Call `mcp_hermes_trading_get_strategy_template` with template_type `smc`, `indicator`, or `hybrid`
3. Modify the template code to implement your idea
4. Call `mcp_hermes_trading_create_strategy` with the name and code
5. Call `mcp_hermes_trading_run_full_backtest` with your new strategy_type name
6. If APPROVED: add it to the scan phase setup type rotation
7. If REJECTED: analyse why (too many false signals? wrong session? etc.) and iterate

### Built-in Strategies Available

| Name | Logic |
|------|-------|
| `fvg_fill` | Enter on retrace into unmitigated FVG |
| `ob_reaction` | Enter when price revisits Order Block |
| `bos_retest` | Enter on retest of broken structure level |
| `choch_confirm` | Enter immediately at Change of Character |
| `ob_fvg_confluent` | OB and FVG overlap zones only (high probability) |
| `liquidity_sweep_reversal` | Stop hunt then reversal entry |
| `killzone_ob_entry` | OB entry restricted to London/NY killzones only |

### Strategy Development Tips

- Start with the `hybrid` template if you want to combine SMC with indicators
- Always check `valid_sessions` — Asian session rarely works for Gold
- Use `min_bars` to require at least N bars of history before firing
- Test on 1000+ bars for statistically significant results
- Compare new strategies against `ob_fvg_confluent` (current best baseline)
- If win rate > 52% but profit factor < 1.3: your losses are too large — tighten SL logic
- If profit factor > 1.3 but win rate < 52%: entries are good but too infrequent — relax filters

---

## Phase: mtf_scan (multi-timeframe version of scan — use this by default)

1. Call `mcp_hermes_trading_get_market_bars_mtf` with timeframes ["D1","H4","H1","M15","M5"]
2. Establish bias top-down:
   - D1/H4: overall trend, major structure, key S/R
   - H1: intermediate structure, which session context we're in
   - M15: entry-grade SMC structure (OBs, FVGs, BOS/CHoCH)
   - M5: precise entry timing, confirmation candles
3. Only flag a setup as HIGH confidence if M15 structure agrees with H4/D1 bias
4. If M15 disagrees with HTF bias, either skip or flag explicitly as
   "counter-trend scalp" with reduced size and tighter invalidation
5. Call `mcp_hermes_trading_visualise_analysis` to paint the M15 chart
6. Proceed exactly as in the `scan` phase from here (queue setups, write notes)

## Phase: create_skill (turn a described strategy into a permanent skill)

Use this whenever Fahd describes a new strategy or trading idea in plain English.

1. Listen to the description and restate it as clear numbered steps:
   - What data to check (bars, MTF, SMC structures, indicators)
   - What conditions must be true to consider an entry
   - How SL/TP/direction are determined
   - Any session/time restrictions
2. Optionally: call `mcp_hermes_trading_get_strategy_template` and
   `mcp_hermes_trading_create_strategy` to build a backtestable Python version,
   then `mcp_hermes_trading_run_full_backtest` to get real win rate / profit factor
3. Call `mcp_hermes_trading_create_hermes_skill` with:
   - skill_name: a clear snake_case name
   - description: one-line summary
   - steps: the numbered steps from step 1, refined with any backtest results
   - linked_strategy: the Python strategy name if you built one
4. Confirm to Fahd: "Skill '<name>' created — invoke it anytime with /skill <name>"
5. From now on this skill is available in `/skill list` and can be scheduled
   in cron just like the built-in phases
