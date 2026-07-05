---
name: hermes-trading-system
description: "Full lifecycle skill for the Hermes trading stack on Windows/Docker: MT5 bridge, preprocessor, backtester, paper trader, execution, MCP server, dashboard, chart annotations, autonomous monitoring subagent, and error diagnosis."
version: "1.0.0"
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, automation, btcusd, xauusd, mt5, docker, monitoring]
---

# Hermes Trading System

Use this skill whenever the user asks about the Hermes trading system, asks to retest it, diagnose dashboards/endpoints, run QA, use `/analyze`, `/backtest`, `/paper_status`, `/draw_levels`, fix MT5/ZMQ/EA issues, or build an autonomous monitor.

## Summary

This repo/stack is a containerised trading workflow:

- MT5 EA emits market bars and trade signals over ZeroMQ.
- `hermes_mt5_bridge` exposes REST on `localhost:5558`.
- `hermes_preprocessor` enriches bars + computes SMC on `localhost:5559`.
- `hermes_backtester` runs strategy simulations on `localhost:5560`.
- `hermes_paper_trader` manages paper positions on `localhost:5561`.
- `hermes_execution` is the order router / risk gatekeeper on `localhost:5563`.
- `hermes_mcp_bridge` handles chart draws + signal ingestion on `localhost:5562`.
- `hermes_mcp_server` converts those services into MCP tools on `localhost:7779/mcp`.
- `hermes_dashboard` is the Flask UI on `localhost:8080`.

## Symbols

Current base symbol for development/retest is **BTCUSD**. The system also supports XAUUSD, EURUSD, etc. Prefer BTCUSD when the user says “today is Saturday” or explicitly requests BTCUSD.

## Required Environment

- Windows 11 + Git Bash/MSYS
- Docker Desktop running
- Repo: `C:\Users\user\Desktop\hermes_claude`
- MCP config: `C:\Users\user\.hermes\config.yaml` must include:

```yaml
mcp_servers:
  hermes_trading:
    url: http://localhost:7779/mcp
    tools:
      include:
        - get_market_bars
        - get_market_bars_mtf
        - get_account_state
        - get_open_positions
        - get_trading_stats
        - get_trade_history
        - send_paper_trade
        - close_position
        - run_backtest
        - get_smc_analysis
        - get_system_status
        - draw_on_chart
        - visualise_analysis
        - draw_trade_signal
        - run_full_backtest
        - create_hermes_skill
        - list_hermes_skills
        - delete_hermes_skill
        - get_hermes_config
        - list_strategies
        - create_strategy
        - delete_strategy
        - get_strategy_template
```

## Usage

### 1. Health check

```bash
docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'
curl http://localhost:7779/health
curl http://localhost:5558/health
curl http://localhost:5559/health
curl http://localhost:5560/health
curl http://localhost:5561/health
curl http://localhost:5562/health
curl http://localhost:5563/health
curl http://localhost:8080/health
```

Expected healthy state:
- 13+ containers `Up`
- All `/health` endpoints return `200` JSON
- `localhost:5558/health` should ideally report `ea_connected: true` if MT5 is running

### 2. Market data probe

Call MCP tool `get_market_bars` for `BTCUSD` across `M15`, `H1`, `H4`, `D1`:

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_market_bars","arguments":{"instrument":"BTCUSD","timeframe":"M15","n":200}}}
```

Expected result: non-empty list of bars with `source: yfinance` if MT5 is offline.

### 3. SMC analysis

Call MCP tool `get_smc_analysis` for `BTCUSD` across timeframes.

Expected result: object with `fvg`, `order_blocks`, `bos`, `choch`, `liquidity`.

### 4. Backtest

Call MCP tool `run_full_backtest` with:

```json
{"instrument":"BTCUSD","timeframe":"M15","strategy_type":"smc_ob_entry","lookback_bars":500,"risk_pct":1.0}
```

Also try `smc_fvg_fill` and `smc_liquidity_sweep`.

Expected result: real bars count, trades list, `verdict: APPROVED/REJECTED` with non-zero stats.

### 5. Paper status / lifecycle

```bash
curl http://localhost:5561/health
curl http://localhost:5561/stats
curl http://localhost:5561/positions
curl "http://localhost:5561/history?n=10"
```

Send a paper trade via MCP `send_paper_trade`:

```json
{"instrument":"BTCUSD","direction":"BUY","entry_price":107500,"sl":107000,"tp":108800,"lots":0.01,"notes":"retest probe"}
```

Confirm new position appears in `/positions`, then close with `close_position`.

### 6. Draw levels / visualise

Use `draw_on_chart` for simple objects, then `visualise_analysis` to paint all SMC structures.

Expected: `drawn > 0` when structures exist; `0` is valid only when no structures are detected.

## Diagnosis Playbook

### All MCP calls return `Failed to resolve 'preprocessor'/'backtester'/'mcp_bridge'`

**Meaning:** The caller cannot resolve Docker internal hostnames from its current network namespace.

**Common causes after restarts:**
1. Compose network aliases changed or were removed.
2. Service started without expected `container_name` / network alias.
3. Hermes MCP server runs on host, but internal URLs use Docker-only names.

**Quick checks:**
```bash
docker network inspect <project>_default
docker ps --filter name=hermes_preprocessor
docker inspect hermes_preprocessor --format '{{json .NetworkSettings.Networks}}'
```

**Fix path:**
- If services are reachable on `localhost:<port>` from host, update MCP server env to use `http://localhost:5559`, `http://localhost:5560`, etc., instead of `http://preprocessor:5559`.
- Restart the MCP server after env changes.

### `/backtest` returns `404 No matching bar data available`

**Meaning:** Backtester cannot load local bars.

**Common causes:**
1. `/data/market_data` missing in container.
2. Preprocessor unreachable and filesystem fallback empty.
3. Symbol/timeframe filename mismatch (`BTCUSD_M15_*.json`).

**Fix path:**
- Ensure enriched bars exist at `/data/market_data/BTCUSD_M15_*.json`
- Prefer fixing network path to preprocessor first, since it does enrichment.

### `get_system_status` says all services `offline` even though containers are up

**Meaning:** The health-check helper in MCP is hitting Docker-internal names from host context.

**Trust direct `localhost` health probes over `get_system_status` when diagnosing container reachability.**

### Dashboard not showing paper trades / draws

**Meaning:** Either:
1. The dashboard is reading from a data source that wasn’t updated, or
2. The side-effect service call failed silently.

**Fix path:**
- Re-run the action and inspect both the MCP response and container logs:
  ```bash
  docker logs hermes_paper_trader --tail 50
  docker logs hermes_execution --tail 50
  docker logs hermes_mcp_bridge --tail 50
  ```
- If MCP returns error but dashboard shows old state, force a refresh by re-querying `/positions` or `/stats` directly.

## QA Checklist

When asked to QA the system, verify ALL of these and report PASS/FAIL with raw evidence:

1. `docker ps` shows all expected containers `Up`
2. All `/health` endpoints return `HTTP 200`
3. `get_market_bars` returns non-empty bar list for `BTCUSD M15`
4. `get_market_bars` returns non-empty bar list for `BTCUSD H1`
5. `get_market_bars` returns non-empty bar list for `BTCUSD H4`
6. `get_market_bars` returns non-empty bar list for `BTCUSD D1`
7. `get_smc_analysis` returns object for `BTCUSD M15` (structures may be empty)
8. `get_smc_analysis` returns object for `BTCUSD H1`
9. `get_smc_analysis` returns object for `BTCUSD H4`
10. `get_smc_analysis` returns object for `BTCUSD D1`
11. `run_full_backtest smc_ob_entry` returns real result, not 404 or DNS error
12. `run_full_backtest smc_fvg_fill` returns real result
13. `run_full_backtest smc_liquidity_sweep` returns real result
14. `/stats` returns numeric `total_trades`, `win_rate`, `profit_factor`
15. `/positions` returns list, not 5xx
16. `send_paper_trade` returns a position object, not connection error
17. Position appears in `/positions` after send
18. `close_position` completes successfully
19. `draw_on_chart` returns success for at least 1 object
20. `.hermes/config.yaml` includes `hermes_trading` MCP server
21. `docker logs hermes_paper_trader` shows `Broker received signal`
22. `docker logs hermes_mcp_bridge` shows draw or signal activity relevant to test

Write failures to `reports/qa_report_<YYYYMMDD_HHMMSS>.md` with exact raw outputs.

## Dashboard / Side-Effect Reconciliation

When an action goes through the system but is not reflected in the dashboard:

1. Inspect MCP response body for success/error.
2. Inspect direct service response (`/positions`, `/stats`, `/history`).
3. Compare timestamps between MCP action and dashboard data fetch.
4. Inspect container logs for the relevant service.
5. If service responded correctly but dashboard reads stale data, document expected polling interval and whether a forced refresh exists.

## Autonomous Monitor Subagent Pattern

Use this pattern when asked to monitor system/dashboard/containers.

### When to use
- “Monitor the system”
- “Watch the dashboard”
- “Set up a watcher for containers”

### Pattern

Spawn a leaf subagent with toolsets: `terminal`, `file`, `todo`.

Subagent task shape:
```text
Goal: Monitor Hermes trading system and report state changes / failures.
Context:
- Workdir: C:\Users\user\Desktop\hermes_claude
- Check: docker ps, /health endpoints, paper trader /stats, /positions
- Report: current state, diffs from last check, recommended actions
- Do NOT modify anything without user approval
```

### Suggested cadence
- 5–15 minute intervals for container health.
- After any MT5 session open, re-check `ea_connected` and latest bars freshness.

### Example invocation

```json
{
  "goal": "Run Hermes system monitoring health check.",
  "context": "Workdir: C:\\Users\\user\\Desktop\\hermes_claude. Check docker ps, /health for ports 5558/5559/5560/5561/5562/7779/8080, /stats and /positions on paper trader. Summarise state in 5-10 bullet points.",
  "toolsets": ["terminal", "file"]
}
```

## Common Commands Reference

```bash
# docker
docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'
docker logs <service> --tail 50
docker logs <service> --since 10m

# paper trader
curl http://localhost:5561/health
curl http://localhost:5561/stats
curl http://localhost:5561/positions
curl "http://localhost:5561/history?n=20"

# MCP server health / config
curl http://localhost:7779/health
python -c "import requests,json; r=requests.post('http://localhost:7779/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'get_hermes_config','arguments':{}}}); print(r.status_code); print(r.text)"

# backtest
python -c "import requests,json; r=requests.post('http://localhost:7779/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'run_full_backtest','arguments':{'instrument':'BTCUSD','timeframe':'M15','strategy_type':'smc_ob_entry','lookback_bars':500}}}); print(r.status_code); print(r.text)"

# SMC
python -c "import requests,json; r=requests.post('http://localhost:7779/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'get_smc_analysis','arguments':{'instrument':'BTCUSD','timeframe':'M15','n':300}}}); print(r.status_code); print(r.text)"
```

## Notes

- MT5 EA heartbeat window is 30 seconds. If `ea_connected: false`, that usually means no EA heartbeat in the last 30s, not necessarily a dead bridge.
- Windows scheduled-task proof pattern: avoid invoking `schtasks.exe` directly from Git Bash; use `powershell -NoProfile -ExecutionPolicy Bypass -File <setup.ps1>` or a `.cmd` wrapper.
- Prefer script-file invocation over inline `python -c` with complex quoting on Windows.
