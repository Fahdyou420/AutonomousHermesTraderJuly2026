# Hermes Trading Agent — Windows 11 Deployment Guide
# RTX 4060 | Docker Desktop | Ollama | Python 3.11+

---

## Prerequisites check

Before starting, verify these are installed:

```powershell
docker --version          # Docker Desktop 24+
docker compose version    # v2.x (note: no hyphen)
python --version          # 3.11 or 3.12
ollama --version          # any recent version
node --version            # 18+ (for the React dashboard)
```

---

## PHASE 1 — Extract and configure

**1.1 Extract the zip to a clean folder**

Do NOT extract to Downloads or a path with spaces or brackets.
Use a short clean path:

```powershell
mkdir C:\Hermes
# Extract hermes-trading-agent-FINAL.zip → C:\Hermes\
# You should have: C:\Hermes\Dockerfile, C:\Hermes\docker-compose.yml, etc.
cd C:\Hermes
```

**1.2 Create your .env file**

```powershell
copy nul .env
notepad .env
```

Paste this into Notepad and save:

```
# Required — get a free key at https://aistudio.google.com/apikey
GEMINI_API_KEY=your_key_here

# Your Obsidian vault path — where the agent writes its memory notes
# Use forward slashes or escaped backslashes
OBSIDIAN_VAULT_ROOT=C:/Users/user/Documents/HermesVault

# Optional — override Ollama model (auto-discovered if blank)
# MODEL_ANALYSIS=hermes3
# MODEL_CODE=qwen2.5-coder

# Leave everything else blank — defaults work correctly
```

**1.3 Create the Obsidian vault folder**

```powershell
mkdir "C:\Users\user\Documents\HermesVault"
```

If you already have an Obsidian vault, point `OBSIDIAN_VAULT_ROOT` there instead.
The agent writes to these subfolders (it creates them automatically):
`01_MARKET_STUDIES`, `03_TRADE_JOURNAL`, `04_KNOWLEDGE_BASE`, `05_RND`

---

## PHASE 2 — Pull Ollama models

Hermes needs at least one language model. Open a terminal and run:

```powershell
# Primary model — the agent uses this for all analysis and decisions
# Pick ONE based on your VRAM (RTX 4060 has 8GB):
ollama pull hermes3              # 4.7GB — recommended (matches the agent's name)
# OR
ollama pull llama3.1:8b          # 4.7GB — good alternative
# OR
ollama pull qwen2.5:7b           # 4.4GB — fast, good reasoning

# Embedding model — required for ChromaDB vector search
ollama pull nomic-embed-text     # 274MB — small, required

# Optional code model for strategy generation
ollama pull qwen2.5-coder:7b    # 4.4GB
```

Verify they loaded:
```powershell
ollama list
```

**Important:** Ollama must be running when the agent starts.
It starts automatically on Windows login, but to manually start it:
```powershell
ollama serve
```

---

## PHASE 3 — Windows setup script

Run this once. It installs the Python virtual environment for `hermes_rpc`,
creates all data directories, and adds firewall rules for ZMQ ports.

```powershell
cd C:\Hermes
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

Expected output ends with:
```
[+] Firewall rule added: Hermes RPC 7778 (port 7778)
[+] Firewall rule added: Hermes ZMQ Data 5555 (port 5555)
========================================================
       HERMES WINDOWS SETUP CONCLUDED SUCCESSFULLY!
========================================================
```

If it fails on the venv step, run manually:
```powershell
python -m venv hermes_rpc\.venv
hermes_rpc\.venv\Scripts\pip install -r hermes_rpc\requirements.txt
hermes_rpc\.venv\Scripts\pip install yfinance uvicorn fastapi
```

---

## PHASE 4 — Build Docker containers (first time only)

This downloads all Docker images and builds the Python services.
Takes 5–15 minutes on first run depending on internet speed.

```powershell
cd C:\Hermes
docker compose build --no-cache
```

Watch for errors. The most common ones and fixes:

| Error | Fix |
|-------|-----|
| `cannot connect to Docker daemon` | Open Docker Desktop and wait for it to show "Engine running" |
| `chromadb 0.4.24 not found` | Already pinned in docker-compose.yml, should resolve automatically |
| `npm ERR!` during app build | Run `npm install` first, then `docker compose build` again |

---

## PHASE 5 — MetaTrader 5 setup

**5.1 Install ZMQ library**

- Download `coke5151/mql5-zmq` from GitHub (the type-safe fork)
- Copy the entire `Include/Zmq/` folder into:
  `C:\Users\user\AppData\Roaming\MetaQuotes\Terminal\[ID]\MQL5\Include\Zmq\`
- Copy `libzmq.dll` and `libsodium.dll` into:
  `C:\Users\user\AppData\Roaming\MetaQuotes\Terminal\[ID]\MQL5\Libraries\`

Find your Terminal ID in MT5: File → Open Data Folder.

**5.2 Install and compile the EA**

Copy `ea\HermesEA.mq5` into:
`MQL5\Experts\`

Open MetaEditor (F4 in MT5), open HermesEA.mq5, press **F7** to compile.
Should show: `0 errors, 0 warnings`

**5.3 Install and compile the indicators**

Copy these into `MQL5\Indicators\`:
- `ea\HermesStructure.mq5`
- `ea\HermesSignals.mq5`

Compile both with F7. Each should show 0 errors.

**5.4 Enable DLL imports**

In MT5: Tools → Options → Expert Advisors
- Check: ✅ Allow DLL imports

**5.5 Attach the EA**

- Open an **XAUUSD** chart on **M15** timeframe
- Drag `HermesEA` from Navigator → Expert Advisors onto the chart
- In the EA inputs, leave everything as default (127.0.0.1, port 5555)
- Click OK — the EA should show a smiley face in the top-right corner

**5.6 Attach the indicators**

- Insert → Indicators → Custom → `HermesStructure` on the same chart
- Insert → Indicators → Custom → `HermesSignals` on the same chart
- Leave all inputs as default

---

## PHASE 6 — First launch

Open **4 separate PowerShell windows** and run one command in each:

**Window 1 — Docker stack**
```powershell
cd C:\Hermes
docker compose up
```
Wait until you see all services show `Started server process` or `Running on`.
Takes about 30 seconds.

**Window 2 — Hermes RPC server**
```powershell
cd C:\Hermes
powershell -ExecutionPolicy Bypass -File scripts\start_hermes_rpc.ps1
```
Wait for: `Uvicorn running on http://0.0.0.0:7778`

**Window 3 — Trading MCP server**
```powershell
cd C:\Hermes
powershell -ExecutionPolicy Bypass -File scripts\start_mcp_server.ps1
```
Wait for: `Hermes Trading MCP Server on http://localhost:7779/mcp`

**Window 4 — Keep open for commands**

---

## PHASE 7 — Verify everything is running

```powershell
# All 12 Docker containers should show "Up"
docker compose ps

# RPC server should respond
curl http://localhost:7778/health

# MCP server should respond
curl http://localhost:7779/health

# Dashboard
curl http://localhost:8080/api/status

# React dashboard
Start-Process "http://localhost:3000"

# Flask terminal
Start-Process "http://localhost:8080/terminal"
```

The status endpoint should return something like:
```json
{
  "chromaDb": "connected",
  "hermesRpc": "connected",
  "ollama": "connected",
  "redis": "connected",
  "obsidian": "connected",
  "mt5Zmq": {"data": "disconnected"}
}
```

`mt5Zmq` shows disconnected until the EA sends its first bar. Attach it to XAUUSD M15 and wait for the next M15 candle to close (or test immediately — see below).

---

## PHASE 8 — Connect Hermes Desktop Agent

This is where the autonomous behavior comes from.

**8.1 Set the model**

Open Hermes Desktop → Settings → Model:
- Provider: `Custom / Ollama`
- Base URL: `http://localhost:11434/v1`
- API Key: `ollama` (any string works)
- Model: type exactly what `ollama list` showed (e.g. `hermes3`)

**8.2 Copy the SOUL.md**

```powershell
copy C:\Hermes\hermes_config\SOUL.md "$env:USERPROFILE\.hermes\SOUL.md"
```

**8.3 Copy the trading skill**

```powershell
mkdir "$env:USERPROFILE\.hermes\skills" -Force
copy C:\Hermes\hermes_config\skills\smc_trading_cycle.md "$env:USERPROFILE\.hermes\skills\"
```

**8.4 Register the MCP server**

Open `C:\Users\user\.hermes\config.yaml` in Notepad.
If the file doesn't exist, create it. Paste the contents of:
`C:\Hermes\hermes_config\config_block.yaml`

The critical section that must be present:
```yaml
mcp_servers:
  hermes_trading:
    url: http://localhost:7779/mcp
```

**8.5 Test the connection**

In Hermes Desktop chat, type:
```
Use the smc_trading_cycle skill, phase: status
```

You should get back a live report of all services, open positions (empty for now), and account stats.

**8.6 Set up the cron schedule** (how Hermes runs autonomously)

In Hermes Desktop, find the Scheduler/Cron section and add:

| Schedule | Command |
|----------|---------|
| `*/15 * * * *` | `Use the smc_trading_cycle skill, phase: scan. Then phase: monitor.` |
| `0 */4 * * *` | `Use the smc_trading_cycle skill, phase: research.` |
| `0 22 * * *` | `Use the smc_trading_cycle skill, phase: review.` |

Once these are set, Hermes runs completely on its own.

---

## PHASE 9 — Quick test (without waiting for a bar close)

To verify the full pipeline works on a Saturday / weekend / no-tick situation:

```powershell
# Send a fake bar directly to the bridge — simulates what the EA does
python -c "
import zmq, json, time
ctx = zmq.Context()
sock = ctx.socket(zmq.PUSH)
sock.connect('tcp://127.0.0.1:5555')
sock.send_string(json.dumps({
    'type': 'bar_event',
    'instrument': 'XAUUSD',
    'timeframe': 'PERIOD_M15',
    'timestamp': int(time.time()),
    'open': 3320.0, 'high': 3325.0, 'low': 3318.0, 'close': 3322.0,
    'volume': 1500, 'spread': 18, 'session': 'london'
}))
print('Test bar sent')
sock.close()
"
```

Then check `http://localhost:8080/api/status` — `mt5Zmq.data` should show `connected`.

In Hermes Desktop, run:
```
Use the smc_trading_cycle skill, phase: scan
```

The agent will pull XAUUSD bars (from MT5 bridge if connected, yfinance if not),
run full SMC analysis, draw structures on the MT5 chart, and write a scan note to
your Obsidian vault.

---

## Daily startup (after first-time setup)

Once everything is set up, starting the system each day is:

```powershell
cd C:\Hermes
docker compose up -d
powershell -ExecutionPolicy Bypass -File scripts\start_hermes_rpc.ps1
powershell -ExecutionPolicy Bypass -File scripts\start_mcp_server.ps1
```

Or just use `start_all.ps1` which does all three automatically.

Attach HermesEA to XAUUSD M15 in MT5. Open Hermes Desktop. Done.

---

## Stopping everything

```powershell
cd C:\Hermes
powershell -ExecutionPolicy Bypass -File scripts\stop_all.ps1
```

Or just close all the PowerShell windows and run `docker compose down`.

---

## Ports reference

| Port | What | Who connects |
|------|------|-------------|
| 3000 | React dashboard | Your browser |
| 5555 | ZMQ data (EA → bridge) | MT5 EA pushes bars here |
| 5556 | ZMQ draw (bridge → EA) | Agent sends chart objects |
| 5557 | ZMQ orders (bridge → EA) | Agent sends trade commands |
| 5558 | mt5_bridge HTTP | Internal Docker calls |
| 5561 | paper_trader HTTP | Internal + dashboard |
| 6379 | Redis | Internal Docker |
| 7778 | hermes_rpc | Hermes Desktop + MCP server |
| 7779 | Trading MCP server | Hermes Desktop Agent |
| 8000 | ChromaDB | Internal Docker |
| 8080 | Flask dashboard | Your browser |
| 11434 | Ollama | hermes_rpc + Docker services |

---

## Troubleshooting

**"Cannot connect to Ollama"**
Run `ollama serve` in a terminal and leave it open.
Also make sure Ollama is not bound to 127.0.0.1 only — check:
```powershell
# Docker needs to reach Ollama via host.docker.internal
# Set OLLAMA_HOST env var if needed:
$env:OLLAMA_HOST = "0.0.0.0"
ollama serve
```

**"mt5Zmq shows disconnected"**
- Confirm `docker compose ps` shows `hermes_mt5_bridge` as Up
- Run the fake bar test above
- Check MT5 Experts tab — the EA should show `[+] Sockets ready`
- Run: `netstat -ano | findstr :5555` — should show LISTENING

**"Embedder keeps restarting"**
This was fixed — ChromaDB is pinned to 0.4.24 in docker-compose.yml.
Run `docker compose build --no-cache` if you're on an old build.

**"hermes_rpc says model not found"**
The model is auto-discovered from `ollama list`. Check what models you have:
```powershell
ollama list
```
If empty, pull a model first (`ollama pull hermes3`).

**Dashboard shows all disconnected**
Check the RPC and MCP server windows are still running.
They must stay open — they're not background services, they're foreground processes.
