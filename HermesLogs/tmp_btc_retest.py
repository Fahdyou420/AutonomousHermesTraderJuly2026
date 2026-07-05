import requests, json, subprocess, shlex, time

BASE = "http://localhost:7779/mcp"

def mcp_tool(name, args=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}
    print(f"\n=== MCP TOOL: {name} ===")
    print(json.dumps(args or {}, ensure_ascii=True))
    r = requests.post(BASE, json=payload, timeout=60, headers={"Content-Type":"application/json"})
    print(f"HTTP {r.status_code}")
    print(r.text[:6000])
    return r.status_code, r.text

print("========= STEP 1 SYSTEM HEALTH / STATUS =========", flush=True)
# docker ps already taken; summary inserted later.

# System status from MCP
mcp_tool("get_hermes_config")
mcp_tool("get_system_status")

print("\n========= STEP 2 MARKET DATA =========", flush=True)
for tf in ["M15","H1","H4","D1"]:
    mcp_tool("get_market_bars", {"instrument":"BTCUSD","timeframe":tf,"n":200})

print("\n========= STEP 3 SMC ANALYSIS =========", flush=True)
for tf in ["M15","H1","H4","D1"]:
    mcp_tool("get_smc_analysis", {"instrument":"BTCUSD","timeframe":tf,"n":300})

print("\n========= STEP 4 BACKTESTS =========\n", flush=True)
for strat in ["smc_ob_entry", "smc_fvg_fill", "smc_liquidity_sweep"]:
    mcp_tool("run_full_backtest", {
        "instrument": "BTCUSD",
        "timeframe": "M15",
        "strategy_type": strat,
        "lookback_bars": 4000,
        "risk_pct": 1.0
    })

print("\n========= STEP 5 PAPER STATUS =========", flush=True)
r = requests.get("http://localhost:5561/health", timeout=10)
print("\n--- /health ---")
print(f"HTTP {r.status_code}")
print(r.text[:1000])
r = requests.get("http://localhost:5561/stats", timeout=10)
print("\n--- /stats ---")
print(f"HTTP {r.status_code}")
print(r.text[:1000])
r = requests.get("http://localhost:5561/positions", timeout=10)
print("\n--- /positions ---")
print(f"HTTP {r.status_code}")
print(r.text[:1000])

print("\n========= STEP 6 PAPER TRADE LIFECYCLE =========", flush=True)
# 6a send
print("\n--- send_paper_trade ---")
mcp_tool("send_paper_trade", {"instrument":"BTCUSD","direction":"BUY","entry_price":107500.0,"sl":107000.0,"tp":108800.0,"lots":0.01,"notes":"BTCUSD retest probe"})

# 6b positions after send
r = requests.get("http://localhost:5561/positions", timeout=10)
print("\n--- positions after send ---")
print(f"HTTP {r.status_code}\n{r.text[:1500]}")

# 6c history / stats
r = requests.get("http://localhost:5561/history?n=10", timeout=10)
print("\n--- /history ---")
print(f"HTTP {r.status_code}\n{r.text[:1500]}")

# 6d close any open for clean end state
r = requests.get("http://localhost:5561/positions", timeout=10)
if r.status_code == 200:
    try:
        pos = r.json()
        if isinstance(pos, list):
            for p in pos:
                tid = p.get("id") or p.get("position_id") or p.get("ticket")
                if tid is not None:
                    print(f"\n--- close_position {tid} ---")
                    mcp_tool("close_position", {"ticket": str(tid)})
    except Exception as e:
        print("close failed", e)

print("\n========= STEP 7 DRAW LEVELS =========", flush=True)
# placeholder draw
mcp_tool("draw_on_chart", {"type":"hline","id":"HERMES_RETEST_HIGH","cmd":"draw","price1":110000.0,"price2":110000.0,"color":"red","label":"retest high"})
mcp_tool("draw_on_chart", {"type":"hline","id":"HERMES_RETEST_LOW","cmd":"draw","price1":105000.0,"price2":105000.0,"color":"green","label":"retest low"})
mcp_tool("visualise_analysis", {"instrument":"BTCUSD","timeframe":"M15","n":300,"clear_first":True,"bias":"NEUTRAL"})

print("\n========= STEP 8 CONFIG AUDIT =========", flush=True)
for path in ["C:/Users/user/Desktop/hermes_claude/.agent-config.json","C:/Users/user/.hermes/config.yaml"]:
    print(f"\n--- {path} ---")
    try:
        import pathlib
        p = pathlib.Path(path)
        print(p.read_text(encoding="utf-8")[:4000])
    except Exception as e:
        print("UNABLE:", e)

# execution service probes if any local execution ports known

print("\n========= RETEST COMPLETE =========", flush=True)
