# Hermes Trading Agent

Hermes Trading Agent is a fully autonomous, self-improving quantitative system engineered to execute, monitor, backtest, and refine Smart Money Concepts (SMC) and Inner Circle Trader (ICT) trading strategies on Gold (`XAUUSD`). Combining a Windows 11 trading host with a containerized Linux Docker environment, Hermes establishes a robust, highly modular architecture. It leverages high-performance ZeroMQ sockets to bridge the MetaTrader 5 terminal with an elite quantitative intelligence engine powered by localized LLMs, a reliable Redis publish/subscribe pipeline, and an Obsidian knowledge base.

At its core, Hermes acts as an autonomous quant researcher. It scans market structures (identifying Order Blocks, Fair Value Gaps, and Liquidity Sweeps), formulates or refines execution hypotheses, performs fully automated backtests in historical pipelines, and transitions qualified strategies into paper trading and dry runs. The entire workflow is documented continuously in a beautifully structured Obsidian knowledge vault that persists the agent's long-term memory, strategies, backtest reports, and operational logs, creating a persistent, self-documenting agentic loop.

Operational control is consolidated in a lightweight, high-frequency dashboard powered by Flask, HTMX, and Server-Sent Events (SSE). The dashboard processes live position telemetry, structure analysis, strategy states, and research jobs directly in the browser with near-zero overhead. This eliminates complex frontend build states and maintains absolute speed and reliability during high-impact market events.

---

## Prerequisites

Before starting, ensure your Windows 11 workstation is equipped with the following dependencies:

1. **Windows 11 Operating System**: Host platform running MetaTrader 5 and the Hermes RPC Server.
2. **Docker Desktop on Windows**: Configured with Linux container support (WSL2 backend) to host the databases and microservice pipelines.
3. **Python 3.11.x**: Native installation on the Windows host (required for local MT5 library interaction and RPC services).
4. **MetaTrader 5 Terminal (MT5)**: Setup and configured to trade `XAUUSD` with a compatible Broker Demo/Live account.
5. **Ollama for Windows** (NOT inside Docker): Installed natively on the host and reachable at `http://host.docker.internal:11434` with `llama3.1:8b` and `qwen2.5-coder:7b` models pulled.
6. **Obsidian App**: Desktop installation pointing to the mounted absolute vault database path.

---

## Quick Start (5 Steps to Deploy)

1. **Clone the Repository**:
   Clone the code package to a dedicated workspace directory on your Windows 11 computer.
   ```bash
   git clone <repository_url> hermes-agent
   cd hermes-agent
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env` at the root folder and configure your system variables:
   ```bash
   copy .env.example .env
   ```
   *Edit the `.env` file to customize absolute paths, AI variables, and keys (see the variables table below).*

3. **Execute Host Setup**:
   Launch a PowerShell window as Administrator, navigate to the project directory, and execute the host installer script. This configures the Python virtual environment and deploys Hermes' system profiles:
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force
   .\scripts\setup_windows.ps1
   ```

4. **Install the MT5 Expert Advisor**:
   Follow instructions in `/ea/README_EA_INSTALL.md` to:
   * Copy `Zmq.mqh` into your MT5 `MQL5\Include\Zmq\` folder.
   * Place `libzmq.dll` and `libsodium.dll` in your MT5 `MQL5\Libraries\` folder.
   * Place `HermesEA.mq5` in `MQL5\Experts\` and compile it.
   * Attach the active `HermesEA` to a **XAUUSD M15** chart. Ensure DLL imports and Algorithmic Trading are enabled in MT5.

5. **Start the Entire Hermes Ecosystem**:
   Execute the boot script to start the background RPC server, launch all containerized microservices, build the Obsidian directory structure, and open the system dashboard in your browser:
   ```powershell
   .\scripts\start_all.ps1
   ```
   *Open your browser and navigate to `http://localhost:8080` to manage your autonomous SMC quantitative system.*

---

## System Architecture

The Hermes Trading Agent system separates operations into distinct layers, ensuring that computationally heavy quantitative processes and local Windows API calls do not block risk-sensitive algorithmic entry logic.

| Layer / Service | Core Purpose | Core Technology | Communication Protocol |
|:---|:---|:---|:---|
| **MT5 Terminal (EA)** | Price feed streams (Ticks & Candles), direct broker order dispatch, canvas overlays. | MQL5, ZeroMQ Library / DLL | ZeroMQ sockets (`TCP 5555`/`5556`/`5557`) |
| **Windows Host RPC** | Direct files manipulation, local execution handles, scrape calendar, read/write local configurations. | Python 3.11, FastAPI / Uvicorn | HTTP REST (`7778`), host.docker.internal |
| **Redis Broker** | High frequency publish/subscribe event routing, message broker. | Redis (7-alpine container) | redis://redis:6379 |
| **ChromaDB Index** | Strategy embedding memory store, historical SMC structure logs. | ChromaDB (alpine container) | http://chromadb:8000 |
| **SMC Preprocessor**| Identifies structural trends: Swing highs, order blocks, structural shifts, voids. | Python 3.11, Pandas, Numpy | Redis event subscription, ZMQ receiver |
| **Backtester** | Simulates strategies locally, optimizes entry weights dynamically. | Python 3.11, VectorBt/Pandas | Redis pub/sub queue commands |
| **Paper Trader** | Risk-neutral model simulations on real-time feeds without money at stake. | Python 3.11, State machine | Redis memory state synchronization |
| **Execution Engine** | Hard risk controls, automated order safety approvals, trailing SL/TP limits. | Python 3.11, Risk limits | Redis Pub/Sub, ZMQ Order router |
| **Dashboard** | Operation panel, live telemetry charting, paper journals, hypothesis sandbox. | Flask, HTMX, Tailwind, SSE | HTTP (`localhost:8080`), Event stream |

---

## Environment Variables Reference

Configure these parameters within your local `.env` file at the root folder:

```env
# Core Systems Environment
LOG_LEVEL=INFO
REDIS_URL=redis://redis:6379
CHROMADB_URL=http://chromadb:8000
HERMES_RPC_URL=http://host.docker.internal:7778

# Obsidian Knowledge Base Path (Absolute path on the Windows host)
# Note: In docker, this mounts to /data/obsidian. Specify the actual Windows path here.
OBSIDIAN_VAULT_PATH=C:\Fahd data AI\Fahd\Vault

# AI / Quantitative Language Models Setup
OLLAMA_HOST=http://host.docker.internal:11434
PRIMARY_MODEL=llama3.1:8b
CODER_MODEL=qwen2.5-coder:7b

# Risk & Compliance Strict Limits
MAX_RISK_PER_TRADE_PCT=1.0
MAX_DAILY_DRAWDOWN_PCT=4.0
MAX_WEEKLY_DRAWDOWN_PCT=8.0
MAX_SPREAD_TOLERANCE_PIPS=25
TRADING_INSTRUMENT=XAUUSD
```

---

## Staged Trust Model (Autonomous Graduation Pipeline)

To protect capital and guarantee algorithmic safety, Hermes executes strategies through a structural **Staged Trust Model**. No strategy or trade sequence can graduate to human-allocated live capital without sequentially executing and clearing verification gates.

```
 [ Hypothesis ] ──▷ [ Backtest Check ] ──▷ [ Paper Trading ] ──▷ [ Live Candidate ] ──▷ [ Live Broker Execution ]
```

1. **Hypothesis**: The autonomous controller or user drafts a Smart Money Concept thesis (e.g., FVG liquidity sweep entries during London open). It is logged as an input note in Obsidian under `05_RND/hypotheses`.
2. **Backtest**: The quantitative machine automatically parses parameters, generates MQL5/Python conditions, backtests historical gold price ticks, and compiles an audit report in `05_RND/results` to evaluate expectancy.
3. **Paper**: If evaluation logs a positive mathematical expectancy (e.g. Win Rate > 45%, R:R > 1:2), it graduates to full demo paper simulation. Real ticks stream into the paper engine via MT5 sockets (mock SL/TP execution logs to `03_TRADE_JOURNAL/paper_trades`).
4. **Live Candidate**: After achieving a stable positive tracking metric over a 14-day trailing cycle (Drawdowns strictly `< 4%`, positive net yield), the strategy publishes a live authorization contract invitation.
5. **Live**: Requires explicit hand-shaken multi-factor human key authorization, at which point the core rule engine permits routing active executions to MT5's live broker socket terminals.

---

## Troubleshooting Guide

### 1. ZeroMQ Socket Communication Fails (EA cannot connect)
* **Status**: MetaTrader 5 terminal console logs `Socket creation failed` or socket initialization hangs.
* **Root Cause & Fix**:
  1. The host dashboard or docker services aren't running yet. Run `.\scripts\start_all.ps1`.
  2. The local firewall is blocking internal port communications. Grant Windows Firewall permissions to loopback interfaces on ports `5555`, `5556`, and `5557`.
  3. Ensure DLL imports are flagged as "Allowed" in MT5 Settings -> Expert Advisors tab.

### 2. Ollama is Not Responding to Container Services
* **Status**: Microservices print `ConnectionRefusedError: host.docker.internal:11434`.
* **Root Cause & Fix**:
  Ollama is running locally but bound exclusively to `127.0.0.1`. You must configure Ollama to listen on all interfaces. In Windows, set the environment variable `OLLAMA_HOST=0.0.0.0:11434` in system environment variables, restart the Ollama app from the background try, and confirm in PowerShell via `curl http://localhost:11434/api/tags`.

### 3. ChromaDB Vector Database is Empty or Fails to Initialize
* **Status**: Ingestor or embedder logs show database timeout or vector registry index missing.
* **Root Cause & Fix**:
  Check if `hermes_chromadb` container is up by typing `docker ps`. If it crashed due to memory limits, increase Docker Desktop's resource allocations to at least 4GB RAM. Check if any local directory conflicts block write locks.

### 4. Hermes Host RPC Server is Unreachable from inside Docker
* **Status**: Docker microservices log `Errno -3: Temporary failure in name resolution` for `host.docker.internal`.
* **Root Cause & Fix**:
  Windows Subsystem for Linux (WSL2) resolver is not propagating the host IP. Add `extra_hosts` lookup explicitly to your `docker-compose.yml` (our pre-packaged configuration resolves this via `host.docker.internal:host-gateway`). Ensure your WSL configuration (`C:\Users\<user>\.wslconfig`) does not override networking behavior to DNS configurations that ignore container interfaces.

### 5. Expert Advisor (EA) is Connected but Not Forwarding Raw Tick Feeds
* **Status**: Connected indicator is active in MT5, but the preprocessor logs show zero received packets on port `5555`.
* **Root Cause & Fix**:
  Make sure your MT5 Market Watch is receiving active tick feeds from your broker (confirm inside the terminal that active price movement exists). Check if the chart you attached the EA to is set to `XAUUSD` and active. Ensure standard market session matches trading times.

### 6. Paper Trading Terminal and SSE Data Feeds do not Update
* **Status**: The web dashboard layout is frozen, showing old positions, and does not update trade telemetry dynamically.
* **Root Cause & Fix**:
  The dashboard retrieves live updates using Server-Sent Events (SSE). If a proxy block or antivirus is blocking persistent HTTP stream handles, the connection closes. Navigate to the page, open Chrome DevTools Console, and verify if connection loops report `EventSource` failures. Ensure the dashboard container `hermes_dashboard` is actively bound to host port `8080`.

### 7. Obsidian Vault Fails to Write Notes or Reports
* **Status**: Logs show `FilePermissionError` or directories are missing when running the initialization script.
* **Root Cause & Fix**:
  1. The path declared in `.env` for `OBSIDIAN_VAULT_PATH` is incorrect or utilizes wrong slash marks. Ensure it represents a valid absolute local Windows directory path without trailing slashes.
  2. If running inside Docker, ensure the path mapped in `docker-compose.yml` mounts precisely to `/data/obsidian`. Restart Docker after altering mount paths.

### 8. Docker host.docker.internal does not Resolve on Windows 11 Home
* **Status**: Containers launch, but failed handshakes occur across all service interfaces.
* **Root Cause & Fix**:
  On certain versions of Windows, WSL2 DNS lookups require fallback definitions. You can replace `host.docker.internal` with your Windows host's actual local Ethernet adapter IP (e.g. `192.168.1.X`) in your `.env` configuration file, allowing containers to route direct LAN traffic back to the host RPC listener.

---

## Contributing

1. Create a conceptual feature branch reflecting your quantitative or rule updates.
2. Ensure compliance checks against the risk variables are fully preserved.
3. Write clean unit test routines for execution gates before merging into the production branch.
4. Update the Obsidian structure profile log in case you introduce new directory nodes.

---

## License

This software package is optimized for private trading installations and custom quantitative development ecosystems. It is licensed under the MIT License.
