import sys, json, requests

BASE = "http://localhost:7779/mcp"

def mcp_tool(name, arguments=None):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }
    print(f"\n===== MCP TOOL CALL: {name} =====", flush=True)
    print(f"REQUEST PAYLOAD: {json.dumps(payload)}", flush=True)
    r = requests.post(BASE, json=payload, timeout=60, headers={"Content-Type": "application/json"})
    print(f"HTTP {r.status_code}", flush=True)
    text = r.text
    print(text[:4000], flush=True)
    return r.status_code, text

# /analyze equivalent: get SMC analysis + bars
mcp_tool("get_market_bars", {"instrument":"XAUUSD","timeframe":"M15","n":300})
mcp_tool("get_smc_analysis", {"instrument":"XAUUSD","timeframe":"M15","n":300})

# /backtest equivalent
mcp_tool("run_full_backtest", {"instrument":"XAUUSD","timeframe":"M15","strategy_type":"smc_ob_entry","lookback_bars":500,"risk_pct":1.0})

# /paper_status equivalent
print("\n===== PAPER STATUS /health =====", flush=True)
try:
    r = requests.get("http://localhost:5561/health", timeout=10)
    print(f"HTTP {r.status_code}", flush=True)
    print(r.text[:2000], flush=True)
except Exception as e:
    print(str(e), flush=True)

print("\n===== PAPER STATUS /stats =====", flush=True)
try:
    r = requests.get("http://localhost:5561/stats", timeout=10)
    print(f"HTTP {r.status_code}", flush=True)
    print(r.text[:2000], flush=True)
except Exception as e:
    print(str(e), flush=True)

print("\n===== PAPER STATUS /positions =====", flush=True)
try:
    r = requests.get("http://localhost:5561/positions", timeout=10)
    print(f"HTTP {r.status_code}", flush=True)
    print(r.text[:2000], flush=True)
except Exception as e:
    print(str(e), flush=True)

# /draw_levels equivalent
mcp_tool("visualise_analysis", {"instrument":"XAUUSD","timeframe":"M15","n":300,"clear_first":True,"bias":"NEUTRAL"})
