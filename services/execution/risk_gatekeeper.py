import os
import sys
import time
import requests
from typing import List, Dict, Any, Tuple

# Ensure correct python path for shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.shared.logger import get_logger
from services.shared.models import TradeSignal

logger = get_logger("risk_gatekeeper")

class RiskGatekeeper:
    def __init__(self):
        self.mt5_bridge_url = os.getenv("MT5_BRIDGE_URL", "http://mt5_bridge:5558")
        self.max_daily_dd = float(os.getenv("MAX_DAILY_DD_PCT", "4.0"))
        self.max_weekly_dd = float(os.getenv("MAX_WEEKLY_DD_PCT", "8.0"))
        self.max_spread_pips = float(os.getenv("MAX_SPREAD_PIPS", "25.0"))

    def check(
        self, 
        signal: Any, 
        account_state: Dict[str, Any], 
        open_positions: List[Dict[str, Any]], 
        calendar_events: List[Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """
        Runs exhaustive risk qualification gates on an incoming trade candidate.
        Returns: Tuple(bool authorized, str rejection_reason)
        """
        # Resolve fields regardless if signal is dataclass or dictionary
        instrument = signal.instrument if hasattr(signal, "instrument") else signal.get("instrument", "")
        direction = signal.direction if hasattr(signal, "direction") else signal.get("direction", "")
        entry_price = float(signal.entry_price if hasattr(signal, "entry_price") else signal.get("entry_price", 0.0))
        lots = float(signal.lots if hasattr(signal, "lots") else signal.get("lots", 0.0))
        mode = signal.mode if hasattr(signal, "mode") else signal.get("mode", "paper")
        confidence = (signal.confidence if hasattr(signal, "confidence") else signal.get("confidence", "medium")).lower()
        r_ratio = float(signal.r_ratio if hasattr(signal, "r_ratio") else signal.get("r_ratio", 0.0))

        logger.info(f"Checking Risk rules for TradeSignal direction: {direction} | Mode: {mode} | Sym: {instrument}")

        # 1. Check Daily Drawdown
        daily_dd = float(account_state.get("daily_dd_pct", 0.0))
        if daily_dd >= self.max_daily_dd:
            return False, f"Rule 1: Daily drawdown limit exceeded. Active: {daily_dd}%, Max: {self.max_daily_dd}%"

        # 2. Check Weekly Drawdown
        weekly_dd = float(account_state.get("weekly_dd_pct", 0.0))
        if weekly_dd >= self.max_weekly_dd:
            return False, f"Rule 2: Weekly drawdown limit exceeded. Active: {weekly_dd}%, Max: {self.max_weekly_dd}%"

        # 3. Max active positions check
        if len(open_positions) >= 3:
            return False, f"Rule 3: Maximum open positions limit (3) exceeded. Active Open count: {len(open_positions)}"

        # 4. Total trade value within 1% of account state balance limit
        balance = float(account_state.get("balance", 10000.0))
        trade_val = lots * entry_price
        max_allowed_val = balance * 0.01
        if trade_val > max_allowed_val:
            return False, f"Rule 4: Position value ({trade_val:.2f}) exceeds 1% of total account balance limit ({max_allowed_val:.2f})"

        # 5. Check macroeconomic calendar impact schedule (within ± 15 mins)
        now_ts = int(time.time())
        for ev in calendar_events:
            impact = str(ev.get("impact", "")).lower()
            if impact == "high":
                ev_ts = int(ev.get("timestamp", 0))
                diff_seconds = abs(ev_ts - now_ts)
                if diff_seconds <= 15 * 60:
                    return False, f"Rule 5: Trade near high-impact macroeconomic event schedule: {ev.get('title', 'Economic Event')} (±15 min limit)"

        # 6. Low Confidence Gate (rejected on live modes)
        if mode == "live" and confidence == "low":
            return False, "Rule 6: Rejected Live trade candidate due to low confidence index rating"

        # 7. Reward-Risk ratio gate (live trades must be >= 1.5R)
        if mode == "live" and r_ratio < 1.5:
            return False, f"Rule 7: Rejected Live trade due to subpar minimum reward-to-risk multiple: {r_ratio}R < 1.5R required"

        # 8. Spread Gate filter from active MT5 bridge feed
        try:
            url = f"{self.mt5_bridge_url}/latest_bars?instrument={instrument}&tf=M15&n=1"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                bars_res = resp.json()
                if bars_res:
                    latest_bar = bars_res[-1]
                    spread_points = int(latest_bar.get("spread", 0))
                    # Conver points to standard pips (1 pip = 10 broker points)
                    spread_pips = spread_points / 10.0
                    if spread_pips > self.max_spread_pips:
                        return False, f"Rule 8: Active market spread of {spread_pips} pips exceeds max protective gate: {self.max_spread_pips} pips"
        except Exception as e:
            logger.warning(f"Skipping MT5 spread verification due to retrieval error: {e}")

        logger.info("✓ All risk qualification criteria passed successfully. Approving Trade Candidate.")
        return True, "approved"
