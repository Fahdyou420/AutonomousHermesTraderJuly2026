import os
import sys
import json
import re
from typing import Optional, Dict, Any

# Ensure correct python path for shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.shared.logger import get_logger
from services.shared.models import TradeSignal

logger = get_logger("signal_generator")

class SignalGenerator:
    @staticmethod
    def parse_agent_output(agent_text: str) -> Optional[TradeSignal]:
        """
        Parses structured signal block from Hermes agent string output.
        Scans for JSON contents enclosed inside ```signal ... ``` formatting.
        """
        if not agent_text:
            return None
            
        logger.info("Scanning agent output text for signal block pattern...")
        
        # Seek string between ```signal and ``` blocks
        pattern = r"```signal\s*([\s\S]*?)\s*```"
        match = re.search(pattern, agent_text)
        
        if not match:
            # Fallback to general json code block scan if they didn't write 'signal' explicit
            fallback_pattern = r"```json\s*([\s\S]*?)\s*```"
            match = re.search(fallback_pattern, agent_text)
            
        if not match:
            # Last resort scan of direct raw bracket blocks
            raw_bracket_pattern = r"({[\s\S]*?})"
            match = re.search(raw_bracket_pattern, agent_text)
            
        if not match:
            logger.warning("No signal JSON sequence detected in agent output text.")
            return None
            
        raw_json = match.group(1).strip()
        try:
            data = json.loads(raw_json)
            # Create dataclass representation
            signal = TradeSignal.from_dict(data)
            logger.info(f"Successfully extracted Signal ID: {signal.signal_id} ({signal.direction} {signal.instrument})")
            return signal
        except Exception as e:
            logger.error(f"Error parsing extracted JSON sequence: {e}. Raw sequence: {raw_json}")
            return None

    @staticmethod
    def format_signal(signal: TradeSignal) -> str:
        """
        Renders a cleanly structured log format for printing.
        """
        return (
            f"=== TradeSignal Candidate ===\n"
            f"ID       : {signal.signal_id}\n"
            f"Symbol   : {signal.instrument} ({signal.timeframe})\n"
            f"Side     : {signal.direction.upper()} @ {signal.entry_price}\n"
            f"SL/TP    : {signal.sl} / {signal.tp}\n"
            f"Risk Size: {signal.lots} lot(s) (R-ratio: {signal.r_ratio})\n"
            f"Setup    : {signal.setup_type} ({signal.session} session)\n"
            f"Mode     : {signal.mode.upper()} [Confidence: {signal.confidence.upper()}]\n"
            f"Notes    : {signal.agent_notes}\n"
            f"============================="
        )

    @staticmethod
    def calculate_lots(balance: float, risk_pct: float, entry: float, sl: float, instrument: str) -> float:
        """
        Computes position size in lots based on maximum trade risk configuration.
        XAUUSD contract specifications parameter:
        pip value = 0.01 per 0.01 lot per point (which scales to 1.0 USD risk per 1 full point per 1.0 standard lot).
        Formula: lots = risk_amount / absolute_point_difference
        """
        # Risk percentage to decimal multiplier
        risk_fraction = risk_pct if risk_pct <= 1.0 else (risk_pct / 100.0)
        risk_cash = balance * risk_fraction
        
        points_diff = abs(entry - sl)
        if points_diff <= 0:
            logger.warning(f"Points difference is 0. Returning minimum lot sizes.")
            return 0.01
            
        lots = risk_cash / points_diff
        
        # Round value to 2 decimal places, with protective minimum constraints
        lots = max(0.01, min(100.0, round(lots, 2)))
        logger.info(f"Calculated safety lots sizing for {instrument}: {lots} lots (Risk cash value: ${risk_cash:.2f})")
        return lots
