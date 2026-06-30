import os
import sys
import json
import time
import zmq
from typing import Dict, List, Any

# Ensure correct python path for shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.shared.logger import get_logger
from services.shared.models import DrawCommand, TradeSignal

logger = get_logger("chart_annotator")

REGISTRY_PATH = "/data/trades/draw_registry.json"

class ChartAnnotator:
    def __init__(self):
        # Anchor directory setup
        os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
        
        # Instantiate ZeroMQ connection bindings
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)
        # Prevent infinite block on send if listener is not active
        self.socket.setsockopt(zmq.LINGER, 1000)
        self.socket.setsockopt(zmq.SNDTIMEO, 2000)
        
        # ZeroMQ Draw Socket port 5556 on MT5 host
        self.target_address = os.getenv("DRAW_ZMQ_URI", "tcp://host.docker.internal:5556")
        logger.info(f"Binding Chart Annotator ZMQ socket to {self.target_address}...")
        self.socket.connect(self.target_address)
        
        # Load registry
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """Loads already drawn chart annotation ids to assist surgical cleaning."""
        if os.path.exists(REGISTRY_PATH):
            try:
                with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading drawing registry file: {e}")
        return {}

    def _save_registry(self):
        """Saves current state of drawn annotations to flat file."""
        try:
            with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
                json.dump(self.registry, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving draw registry file: {e}")

    def _register_object_id(self, instrument: str, timeframe: str, object_id: str):
        """Saves object ID to the local tracing index list."""
        if instrument not in self.registry:
            self.registry[instrument] = {}
        if timeframe not in self.registry[instrument]:
            self.registry[instrument][timeframe] = []
        if object_id not in self.registry[instrument][timeframe]:
            self.registry[instrument][timeframe].append(object_id)
        self._save_registry()

    def _send_command(self, cmd: DrawCommand) -> bool:
        """Helper to serialize and transmit DrawCommand over ZeroMQ channel."""
        try:
            payload = cmd.to_dict()
            msg_str = json.dumps(payload)
            self.socket.send_string(msg_str)
            return True
        except Exception as e:
            logger.error(f"Draw command socket transmission failure: {e}")
            return False

    def draw_smc_structures(self, smc_analysis: Dict[str, Any], instrument: str, timeframe: str):
        """
        Iterates all detected SMC structures and dispatches corresponding Draw Commands to MT5.
        - Bullish FVG = green rect
        - Bearish FVG = red rect
        - Bullish OB = blue rect
        - Bearish OB = orange rect
        - BOS = cyan hline
        - CHoCH = magenta hline
        - Liquidity = yellow dotted hline
        """
        logger.info(f"Adding SMC drawing annotations for {instrument} ({timeframe})...")
        now_ts = int(time.time())

        # 1. Fair Value Gaps (FVG)
        for f in smc_analysis.get("fvg", []):
            if f.get("filled"):
                continue
            color = "green" if f["type"] == "bullish" else "red"
            cmd = DrawCommand(
                cmd="draw",
                type="rect",
                id=f["id"],
                price1=float(f["high"]),
                price2=float(f["low"]),
                time1=int(f["time1"]),
                time2=int(f["time2"]),
                color=color,
                style="solid",
                width=1,
                label=f"unfilled_fvg_{f['type']}",
                timeframe=timeframe
            )
            if self._send_command(cmd):
                self._register_object_id(instrument, timeframe, f["id"])

        # 2. Order Blocks
        for ob in smc_analysis.get("order_blocks", []):
            color = "blue" if ob["type"] == "bullish" else "orange"
            cmd = DrawCommand(
                cmd="draw",
                type="rect",
                id=ob["id"],
                price1=float(ob["high"]),
                price2=float(ob["low"]),
                time1=int(ob["timestamp"]),
                time2=now_ts, # extend to current chart point
                color=color,
                style="solid",
                width=1,
                label=f"ob_{ob['type']}",
                timeframe=timeframe
            )
            if self._send_command(cmd):
                self._register_object_id(instrument, timeframe, ob["id"])

        # 3. Breaks of Structure (BOS)
        for b in smc_analysis.get("bos", []):
            cmd = DrawCommand(
                cmd="draw",
                type="hline",
                id=b["id"],
                price1=float(b["level"]),
                price2=float(b["level"]),
                color="cyan",
                style="solid",
                width=1,
                label=f"BOS_{b['type'].upper()}",
                timeframe=timeframe
            )
            if self._send_command(cmd):
                self._register_object_id(instrument, timeframe, b["id"])

        # 4. Changes of Character (CHoCH)
        for c in smc_analysis.get("choch", []):
            cmd = DrawCommand(
                cmd="draw",
                type="hline",
                id=c["id"],
                price1=float(c["level"]),
                price2=float(c["level"]),
                color="magenta",
                style="solid",
                width=1,
                label=f"CHoCH_{c['type'].upper()}",
                timeframe=timeframe
            )
            if self._send_command(cmd):
                self._register_object_id(instrument, timeframe, c["id"])

        # 5. Liquidity Pools
        for liq in smc_analysis.get("liquidity", []):
            cmd = DrawCommand(
                cmd="draw",
                type="hline",
                id=liq["id"],
                price1=float(liq["price"]),
                price2=float(liq["price"]),
                color="yellow",
                style="dotted",
                width=1,
                label=f"Liq_{liq['type'].upper()}",
                timeframe=timeframe
            )
            if self._send_command(cmd):
                self._register_object_id(instrument, timeframe, liq["id"])

        logger.info("✓ Dispatched all SMC drawing indicators successfully.")

    def draw_trade(self, signal: TradeSignal):
        """
        Draws active trade markers directly on user chart windows:
        1. Entry Arrow
        2. SL Line (red dashed hline)
        3. TP Line (green dashed hline)
        """
        instrument = signal.instrument
        timeframe = signal.timeframe
        sig_id = signal.signal_id
        now_ts = int(time.time())

        # Determine Arrow details
        arrow_id = f"arrow_entry_{sig_id}"
        arrow_color = "blue" if signal.direction.lower() in ["long", "buy"] else "red"
        
        # Build entry point marker
        arrow_cmd = DrawCommand(
            cmd="draw",
            type="arrow",
            id=arrow_id,
            price1=signal.entry_price,
            time1=signal.timestamp or now_ts,
            color=arrow_color,
            style="solid",
            width=2,
            label=f"Entry {signal.direction.upper()}",
            timeframe=timeframe
        )
        if self._send_command(arrow_cmd):
            self._register_object_id(instrument, timeframe, arrow_id)

        # Build Stop Loss representation (red dashed)
        sl_id = f"sl_line_{sig_id}"
        sl_cmd = DrawCommand(
            cmd="draw",
            type="hline",
            id=sl_id,
            price1=signal.sl,
            price2=signal.sl,
            color="red",
            style="dashed",
            width=1,
            label=f"SL {signal.sl}",
            timeframe=timeframe
        )
        if self._send_command(sl_cmd):
            self._register_object_id(instrument, timeframe, sl_id)

        # Build Take Profit representation (green dashed)
        tp_id = f"tp_line_{sig_id}"
        tp_cmd = DrawCommand(
            cmd="draw",
            type="hline",
            id=tp_id,
            price1=signal.tp,
            price2=signal.tp,
            color="green",
            style="dashed",
            width=1,
            label=f"TP {signal.tp}",
            timeframe=timeframe
        )
        if self._send_command(tp_cmd):
            self._register_object_id(instrument, timeframe, tp_id)

        logger.info(f"✓ Formatted and sent custom trading boundaries for Signal ID {sig_id}")

    def clear_instrument(self, instrument: str, timeframe: str):
        """
        Clears any previous indicator annotations inside target window.
        Surgically releases specific IDs stored in registry tracking.
        """
        logger.info(f"Clearing drawing history registry for {instrument} ({timeframe})...")
        drawn_objs = self.registry.get(instrument, {}).get(timeframe, [])
        
        # 1. Surgical deletes
        for obj_id in list(drawn_objs):
            cmd = DrawCommand(
                cmd="delete",
                id=obj_id,
                timeframe=timeframe
            )
            self._send_command(cmd)
            
        # 2. General broad clear to capture orphaned objects
        generic_clear = DrawCommand(
            cmd="clear",
            timeframe=timeframe
        )
        self._send_command(generic_clear)

        # Commit trace cleanup resets
        if instrument in self.registry and timeframe in self.registry[instrument]:
            self.registry[instrument][timeframe] = []
            self._save_registry()
            
        logger.info("✓ Finished executing clear processes.")

    def close(self):
        """Clean resource lifecycle teardown."""
        try:
            self.socket.close()
            self.context.term()
        except Exception:
            pass
