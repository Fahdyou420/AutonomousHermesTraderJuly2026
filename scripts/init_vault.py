#!/usr/bin/env python3
"""
Hermes Trading Agent — Obsidian Vault Structure Initializer
Creates the full vault folder structures, template strategy cards, and memory profiles.
"""

import os
import sys
from pathlib import Path

def get_vault_path() -> Path:
    # Default path as per design rules
    vault_dir = "/data/obsidian"
    
    # Check if a custom path is declared in local .env
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if line.startswith("OBSIDIAN_VAULT_PATH="):
                    val = line.split("=", 1)[1].strip()
                    # Strip any surrounding quotes
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    if val:
                        vault_dir = val
                        break
                        
    return Path(vault_dir)

def create_vault():
    vault_base = get_vault_path()
    print(f"[*] Initializing Hermes Obsidian Vault at: {vault_base}")

    # List of directory paths under vault base
    directories = [
        "00_INBOX",
        "01_MARKET_STUDIES/XAUUSD/2025",
        "01_MARKET_STUDIES/XAUUSD/2026",
        "02_STRATEGIES/active",
        "02_STRATEGIES/archive",
        "02_STRATEGIES/templates",
        "03_TRADE_JOURNAL/paper_trades",
        "03_TRADE_JOURNAL/live_trades",
        "04_KNOWLEDGE_BASE/SMC",
        "04_KNOWLEDGE_BASE/ICT",
        "04_KNOWLEDGE_BASE/MACRO",
        "05_RND/hypotheses",
        "05_RND/results",
        "06_AGENT_MEMORY"
    ]

    # Create directories recursively
    for folder in directories:
        folder_path = vault_base / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        print(f"  [+] Created directory: {folder}")

    # Create Strategy Card Template
    strategy_template_content = """# SMC Strategy Card — Template

## Metadata
- **Strategy ID**: SMC_OB_REVERSAL_H1
- **Author**: Hermes Agent v1
- **Current Stage**: hypothesis
- **Associated Instrument**: XAUUSD
- **Reference Timeframes**: H1 (HTF Bias), M15 (LTF Trigger)

## Risk Parameters
- **Max Risk Per Cycle**: 1.0% Max Equity Limit
- **Daily Drawdown Cap**: 4.0%
- **Weekly Drawdown Cap**: 8.0%
- **Max Spread Tolerance**: 25 Pips

## Entry Rules Set
1. **Bias Identification**: H1 structure shows Bullish Market Structure Shift (MSS) leaving a Fair Value Gap (FVG).
2. **Zone Refinement**: Locate primary H1 Bullish Order Block (OB) below the 50% discount level of the impulse leg.
3. **Trigger Sweep**: Wait for price to sweep low of the trigger range and enter on M15 bullish structure expansion.

## Exit Management Rules
- **Stop Loss (SL)**: 1 ATR below the trigger Candle Low.
- **Take Profit (TP) 1**: 2.0 R:R Ratio (Liquidity Sweep target).
- **Take Profit (TP) 2**: HTF Swing High liquidity pools.
"""
    
    template_file_path = vault_base / "02_STRATEGIES/templates/strategy_card_template.md"
    with open(template_file_path, "w", encoding="utf-8") as f:
        f.write(strategy_template_content.lstrip())
    print("  [+] Created file: 02_STRATEGIES/templates/strategy_card_template.md")

    # Create empty MEMORY.md profile
    memory_content = """# Hermes Autonomous Memory Profile

## Agent State Context
- Last Boot Time: 2026-06-08T10:49:26Z
- Instrument Coverage: XAUUSD
- Active Stage Filter: paper

## Core Weights & Model Alignments
- Primary LLM: Llama-3.1-8B-GGUF
- Coding Assist: Qwen-2.5-Coder-Tools

## Execution History & Observations
- No trades processed.
"""
    
    memory_file_path = vault_base / "06_AGENT_MEMORY/MEMORY.md"
    with open(memory_file_path, "w", encoding="utf-8") as f:
        f.write(memory_content.lstrip())
    print("  [+] Created file: 06_AGENT_MEMORY/MEMORY.md")

    # Create empty USER.md profile
    user_content = """# User Preferences Profile

## Preferences
- Name: Fahd
- Target Instrument: XAUUSD Custom SMC
- Preferred Risk Profile: Conservative (Max 1% per Trade Setup)
- Execution Targets: MetaTrader 5 Terminal on host via ZeroMQ sockets
"""
    
    user_file_path = vault_base / "06_AGENT_MEMORY/USER.md"
    with open(user_file_path, "w", encoding="utf-8") as f:
         f.write(user_content.lstrip())
    print("  [+] Created file: 06_AGENT_MEMORY/USER.md")

    print("[*] Obsidian structure initialized successfully.")

if __name__ == "__main__":
    create_vault()
