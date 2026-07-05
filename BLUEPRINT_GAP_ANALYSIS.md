# Hermes Trading Agent - Blueprint Gap Analysis

This document compares the original project specification components (specifically Sections 5.2, 5.3, 5.5, 9.1, and 13) with the current ground truth of the system architecture.

## Component Gap Analysis

| Component | Status | Location / Details |
| :--- | :--- | :--- |
| **Skills (Sec 5.3)** | | |
| `analyse_market_structure` | EXISTS | `~/.hermes/skills/trading/analyse_market_structure.md` |
| `generate_strategy` | EXISTS | `~/.hermes/skills/trading/generate_strategy.md` |
| `run_backtest` | EXISTS | `~/.hermes/skills/trading/run_backtest.md` |
| `write_market_study` | EXISTS | `~/.hermes/skills/trading/write_market_study.md` |
| `review_paper_trades` | EXISTS | `~/.hermes/skills/trading/review_paper_trades.md` |
| `scalp_session_scan` | EXISTS | `~/.hermes/skills/trading/scalp_session_scan.md` |
| **Cron Jobs (Sec 5.5)** | | |
| `nightly_scan` | MISSING | No cron files found in `~/.hermes/crons` |
| `weekly_review` | MISSING | No cron files found in `~/.hermes/crons` |
| `morning_briefing` | MISSING | No cron files found in `~/.hermes/crons` |
| `hypothesis_queue` | MISSING | No cron files found in `~/.hermes/crons` |
| **Context Files (Sec 5.2)** | | |
| `AGENTS.md` | EXISTS | `~/.hermes/AGENTS.md` (Contains Trust Models & Tools) |
| `SOUL.md` | EXISTS | `~/.hermes/SOUL.md` (Identity & Trading Framework) |
| `MEMORY.md` | EXISTS | `~/.hermes/MEMORY.md` (Memory Ledger for rules/lessons) |
| `USER.md` | MISSING | |
| **Staged Trust Model (Sec 13)** | | |
| Stage 0-4 Promotion Pipeline | PARTIAL | Defined structurally in `AGENTS.md` and `SOUL.md` (Stage 1-4 explicitly mapped: Hypothesis -> Backtest -> Paper trade -> Live), but full automation of the stage thresholds (e.g. promoting automatically after 20 trades) is not fully implemented as a Python background task. |
| **Dashboard / R&D Lab (Sec 9.1)**| | |
| R&D Lab Dashboard Panel | EXISTS | Defined in `dashboard/routes/rnd.py` |
| Hypothesis Queue | EXISTS | `/data/rnd/queue.json` (Managed via `rnd.py` routes) |

## Summary
The fundamental integration with Hermes Desktop CLI as the core agent runtime is functioning as intended. The context files (`AGENTS.md`, `SOUL.md`, `MEMORY.md`) and the required agent skills are present and accurately bound to the MCP server. 

The primary gap is the **complete absence of cron jobs** required for automated scanning, reviewing, and hypothesis backtesting without human prompting, as well as the missing `USER.md` context file.
