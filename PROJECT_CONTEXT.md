# Hermes Trading Agent - Project Context

## Ground Truth Configuration
Based on a codebase audit as of July 2026, the current configuration is as follows:

*   **Vault Path:** `C:\Users\user\AppData\Local\hermes\obsidian` (Managed via `OBSIDIAN_VAULT_ROOT` in `.env`)
*   **MCP Server Port:** `7779` (Custom MCP server exposed for Hermes Desktop CLI)
*   **Hermes RPC Port:** `7778` (FastAPI service for auxiliary host-level operations)
*   **Agent Directory:** `C:\Users\user\AppData\Local\hermes\.Hermes`
*   **Skills Directory:** `C:\Users\user\AppData\Local\hermes\skills\trading`

### Core Agent Files (`~/.hermes`)
*   `AGENTS.md`: **Exists**. Defines staging trust models, system tool schema (11 MCP bindings), and strict risk limits (e.g., 1% max risk, 4% daily DD, 8% weekly DD).
*   `SOUL.md`: **Exists**. Defines the agent's identity, SMC/ICT trading framework, risk rules, and trust ladder (Hypothesis -> Backtest -> Paper -> Live).
*   `MEMORY.md`: **Exists**. Serves as the central memory ledger for lessons, heuristics, and anomalies.
*   `USER.md`: **Missing**.
*   `config.yaml`: **Exists**. Configures MCP endpoints and tool behavior.

### Skills & Crons
*   **Skills:** The `skills/trading` folder contains multiple markdown-based skills including `analyse_market_structure.md`, `generate_strategy.md`, `review_paper_trades.md`, `run_backtest.md`, `scalp_session_scan.md`, `write_market_study.md`, and `smc_trading_cycle.md`.
*   **Crons:** No cron job files exist in `~/.hermes/crons`. The agent lacks automated schedule triggers.

---

## Architectural Correction: Hermes Desktop CLI as Runtime
The original project specification assumed building a custom agent orchestration runtime from scratch in Python (e.g., `from agent.agent import HermesAgent`). 

**Mid-project Pivot:**
The actual system utilizes the **Hermes Desktop CLI** (`NousResearch/hermes-agent`) as the native agent runtime. 
*   Hermes Desktop CLI connects to a custom Python-based MCP server (`hermes_mcp_server.py` on port `7779`) which exposes the core trading microservices (Backtester, Paper Trader, Execution, etc.) as callable tools.
*   A separate `hermes_rpc` service on port `7778` handles host-level actions.
*   Consequently, agent orchestration (skills, subagent delegation, memory, and crons) is managed by **configuring Hermes Desktop CLI's native markdown features** (`AGENTS.md`, `SOUL.md`, `skills/` directory), rather than by writing custom Python orchestration loops.

---

## Current Safety & Execution Status
Following recent QA and bug fixes, the execution engine is fully verified:
*   **Risk Gatekeeper:** Verified working. All 8 rules enforce correctly, including the critical Rule 4 (Risk-Distance based lot sizing vs. max risk percentage).
*   **Kill Switch:** Verified working. The system can independently halt trading via API/Redis endpoints.
*   **Idempotency:** Verified working. Duplicate signals are blocked effectively, and the approval mode locking mechanism functions correctly.
*   **Simulation Realism:** Slippage and spread (ask/bid logic) are accurately simulated in the `paper_trader`.
*   **Approval Mode:** Tested and confirmed working (`APPROVAL_REQUIRED` is currently set to `false` in production for autonomous operation).
