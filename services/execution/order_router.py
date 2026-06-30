import os
import sys
import json
import time
import zmq
from typing import Any

# Ensure correct python path for shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.shared.logger import get_logger
from services.shared.models import TradeSignal, OrderCommand

logger = get_logger("order_router")

ORDERS_LOG_FILE = "/data/trades/orders.jsonl"

class OrderRouter:
    def __init__(self):
        # Anchor directory setup
        os.makedirs(os.path.dirname(ORDERS_LOG_FILE), exist_ok=True)
        
        # Instantiate ZeroMQ connection bindings
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)
        # Prevent infinite block on send if listener is not active
        self.socket.setsockopt(zmq.LINGER, 1000)
        self.socket.setsockopt(zmq.SNDTIMEO, 2000)
        
        # ZeroMQ EA host reached from Docker via host.docker.internal
        self.target_address = os.getenv("ORDER_COMMAND_ZMQ_URI", "tcp://host.docker.internal:5557")
        logger.info(f"Binding Order Router ZMQ socket to {self.target_address}...")
        self.socket.connect(self.target_address)

    def _log_order_line(self, command_dict: dict):
        """Append compiled orders to the offline tracker flat file."""
        try:
            with open(ORDERS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": int(time.time()),
                    "command": command_dict
                }) + "\n")
        except Exception as e:
            logger.error(f"Error appending order logs to {ORDERS_LOG_FILE}: {e}")

    def send_order(self, signal: TradeSignal) -> bool:
        """
        Translates a TradeSignal to a compliant OrderCommand and pushes
        down into MT5 via ZMQ. Records event details in local tracking files.
        """
        # Parse standard action code string
        side = signal.direction.lower()
        if side in ["long", "buy"]:
            action = "BUY"
        elif side in ["short", "sell"]:
            action = "SELL"
        else:
            logger.error(f"Unknown signal direction: {signal.direction}")
            return False

        # Build order representation
        # Comment matches signal_id for tracking linkage
        command = OrderCommand(
            cmd="order",
            action=action,
            instrument=signal.instrument,
            lots=signal.lots,
            sl=signal.sl,
            tp=signal.tp,
            comment=signal.signal_id,
            magic=123456 # default magic number
        )
        
        payload = command.to_dict()
        msg_str = json.dumps(payload)
        
        logger.info(f"Routing order payload: {msg_str}")
        
        try:
            # Send message string non-blocking
            self.socket.send_string(msg_str)
            logger.info("[✓] Successfully transmitted Order Command to host!")
            self._log_order_line(payload)
            return True
        except Exception as e:
            logger.error(f"Order socket dispatch failed: {e}")
            # Still log locally for recovery tracing
            self._log_order_line({**payload, "error": str(e)})
            return False

    def send_close(self, trade_id: str, instrument: str) -> bool:
        """
        Translates a closing request to an OrderCommand and routes to broker terminal.
        """
        command = OrderCommand(
            cmd="order",
            action="CLOSE",
            instrument=instrument,
            comment=str(trade_id),
            lots=0.0,
            sl=0.0,
            tp=0.0,
            magic=123456
        )
        
        payload = command.to_dict()
        msg_str = json.dumps(payload)
        
        logger.info(f"Routing close payload: {msg_str}")
        
        try:
            self.socket.send_string(msg_str)
            logger.info(f"[✓] Transmitted direct CLOSE command for target {trade_id} on {instrument}")
            self._log_order_line(payload)
            return True
        except Exception as e:
            logger.error(f"Close command socket dispatch failed: {e}")
            self._log_order_line({**payload, "error": str(e)})
            return False

    def close(self):
        """Clean close resource context."""
        try:
            self.socket.close()
            self.context.term()
        except Exception:
            pass
