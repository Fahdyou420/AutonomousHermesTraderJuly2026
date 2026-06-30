"""
Hermes Strategy Plugin Base Class
===================================
Every custom strategy must inherit from BaseStrategy and implement:
  - name: str            -- unique identifier, used as strategy_type
  - description: str     -- human-readable description
  - find_signal(bars, i, smc) -> dict | None

The backtester calls find_signal() at each bar (index i).
Return a signal dict or None.

Signal dict format:
  {
      "direction": "long" | "short",
      "entry_price": float,
      "setup_id": str,          # unique ID to prevent re-entry
      "notes": str              # shown in trade log
  }

The engine handles SL/TP calculation, lot sizing, risk management,
session filtering, and spread gating — you don't need to implement those.

Available from smc dict:
  smc["fvg"]          - list of FVGs with id, type, high, low, time1, time2, filled
  smc["order_blocks"] - list of OBs with id, type, high, low, timestamp
  smc["bos"]          - list of BOS events with id, type, level, timestamp
  smc["choch"]        - list of CHoCH events
  smc["liquidity"]    - list of liquidity pools

Available indicators (import from services.preprocessor.indicators):
  atr(bars, period)      -> list of floats
  ema(bars, period)      -> list of floats
  rsi(bars, period)      -> list of floats
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class BaseStrategy(ABC):

    name: str = "base"
    description: str = "Base strategy — do not use directly"
    author: str = "Hermes Agent"
    version: str = "1.0"

    # Which sessions this strategy is valid for.
    # Override in subclass. Empty list = all sessions.
    valid_sessions: List[str] = []

    # Minimum bars required before this strategy can fire.
    min_bars: int = 50

    @abstractmethod
    def find_signal(
        self,
        bars: List[Dict[str, Any]],
        i: int,
        smc: Dict[str, Any],
        triggered_ids: set
    ) -> Optional[Dict[str, Any]]:
        """
        Called for each bar at index i.
        bars[i] is the current bar.
        bars[:i] is historical (no lookahead).
        smc contains all pre-computed structures.
        triggered_ids is the set of structure IDs already used — add yours to prevent re-entry.

        Return signal dict or None.
        """
        pass

    def should_run(self, session: str) -> bool:
        """Check if strategy is valid in the current session."""
        if not self.valid_sessions:
            return True
        return session in self.valid_sessions
