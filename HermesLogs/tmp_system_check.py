import requests, json, time, os

BASE = "http://localhost:7779/mcp"
HEADERS = {"Content-Type": "application/json"}

def mcp_tool(name, args=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}
    r = requests.post(BASE, json=payload, timeout=30)
    print(f"\n=== MCP {name} ===\nHTTP {r.status_code}\n{r.text[:4000]}", flush=True)
    return r.status_code, r.text

print("===== STEP 1 SYSTEM HEALTH CHECK =====", flush=True)

print("\n--- docker ps ---", flush=True)
try:
    import subprocess, shlex
    p = subprocess.run(shlex.split("docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'"), capture_output=True, text=True, timeout=20)
    print(p.stdout)
    if p.stderr:
        print("STDERR:", p.stderr)
except Exception as e:
    print("docker ps failed:", e)

# Hermes app health via mcp server
mcp_tool("get_hermes_config")
mcp_tool("get_system_status")

# service direct endpoints
for url in ["http://localhost:7779/health","http://localhost:5560/health","http://localhost:5561/health","http://localhost:5559/health","http://localhost:5558/health","http://localhost:5562/health"]:
    print(f"\n--- GET {url} ---", flush=True)
    try:
        r = requests.get(url, timeout=10)
        print(f"HTTP {r.status_code}\n{r.text[:2000]}", flush=True)
    except Exception as e:
        print(f"EXCEPTION: {e}", flush=True)

# EA bridge reachability via preprocessed market endpoint
for ep in [("MT5 bridge latest bars","http://localhost:5558/latest_bars?instrument=BTCUSD&tf=M15&n=1"),("preprocessor enriched","http://localhost:5559/enriched?instrument=BTCUSD&tf=M15&n=5")]:
    print(f"\n--- {ep[0]} ---\nGET {ep[1]}", flush=True)
    try:
        r = requests.get(ep[1], timeout=10)
        print(f"HTTP {r.status_code}\n{r.text[:3000]}", flush=True)
    except Exception as e:
        print(f"EXCEPTION: {e}", flush=True)

# approximation of MT5 ZMQ state via logs if any
