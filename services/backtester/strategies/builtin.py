"""
Built-in SMC/ICT strategies — the four original ones refactored as plugins.
These replace the hardcoded elif chains in engine.py.
"""
from typing import Dict, Any, Optional, List
from .base import BaseStrategy


class FVGFillStrategy(BaseStrategy):
    name        = "fvg_fill"
    description = "Enter on price retrace into an unmitigated Fair Value Gap (3-candle imbalance). Bullish FVG = BUY, Bearish FVG = SELL."
    valid_sessions = ["london", "newyork", "overlap"]
    min_bars    = 30

    def find_signal(self, bars, i, smc, triggered_ids):
        bar  = bars[i]
        ts   = int(bar.get("timestamp", 0))
        high = float(bar.get("high", 0))
        low  = float(bar.get("low", 0))
        close= float(bar.get("close", 0))

        for fvg in smc.get("fvg", []):
            if fvg["time2"] >= ts:           continue
            if fvg["id"] in triggered_ids:   continue
            if fvg.get("filled"):            continue

            fh, fl = fvg["high"], fvg["low"]
            if fvg["type"] == "bullish" and low <= fh and close >= fl:
                triggered_ids.add(fvg["id"])
                return {"direction": "long", "entry_price": fh,
                        "setup_id": fvg["id"], "notes": "Retrace into bullish FVG"}
            if fvg["type"] == "bearish" and high >= fl and close <= fh:
                triggered_ids.add(fvg["id"])
                return {"direction": "short", "entry_price": fl,
                        "setup_id": fvg["id"], "notes": "Retrace into bearish FVG"}
        return None


class OBReactionStrategy(BaseStrategy):
    name        = "ob_reaction"
    description = "Enter when price revisits an unmitigated Order Block (last opposite candle before BOS)."
    valid_sessions = ["london", "newyork", "overlap"]
    min_bars    = 50

    def find_signal(self, bars, i, smc, triggered_ids):
        bar  = bars[i]
        ts   = int(bar.get("timestamp", 0))
        high = float(bar.get("high", 0))
        low  = float(bar.get("low", 0))
        close= float(bar.get("close", 0))

        for ob in smc.get("order_blocks", []):
            if ob["timestamp"] >= ts:        continue
            if ob["id"] in triggered_ids:    continue

            oh, ol = ob["high"], ob["low"]
            if ob["type"] == "bullish" and low <= oh and close >= ol:
                triggered_ids.add(ob["id"])
                return {"direction": "long", "entry_price": oh,
                        "setup_id": ob["id"], "notes": "Revisited bullish OB"}
            if ob["type"] == "bearish" and high >= ol and close <= oh:
                triggered_ids.add(ob["id"])
                return {"direction": "short", "entry_price": ol,
                        "setup_id": ob["id"], "notes": "Revisited bearish OB"}
        return None


class BOSRetestStrategy(BaseStrategy):
    name        = "bos_retest"
    description = "Enter after a Break of Structure when price pulls back to retest the broken level."
    valid_sessions = ["london", "newyork", "overlap"]
    min_bars    = 50

    def find_signal(self, bars, i, smc, triggered_ids):
        bar  = bars[i]
        ts   = int(bar.get("timestamp", 0))
        high = float(bar.get("high", 0))
        low  = float(bar.get("low", 0))
        close= float(bar.get("close", 0))

        for bos in smc.get("bos", []):
            if bos["timestamp"] >= ts:       continue
            if bos["id"] in triggered_ids:   continue

            lvl = bos["level"]
            if bos["type"] == "bullish" and low <= lvl and close > lvl:
                triggered_ids.add(bos["id"])
                return {"direction": "long", "entry_price": lvl,
                        "setup_id": bos["id"], "notes": "Retest of bullish BOS level"}
            if bos["type"] == "bearish" and high >= lvl and close < lvl:
                triggered_ids.add(bos["id"])
                return {"direction": "short", "entry_price": lvl,
                        "setup_id": bos["id"], "notes": "Retest of bearish BOS level"}
        return None


class CHoCHConfirmStrategy(BaseStrategy):
    name        = "choch_confirm"
    description = "Enter immediately in the direction of a Change of Character (first sign of trend reversal)."
    valid_sessions = ["london", "newyork", "overlap"]
    min_bars    = 30

    def find_signal(self, bars, i, smc, triggered_ids):
        bar = bars[i]
        ts  = int(bar.get("timestamp", 0))

        for choch in smc.get("choch", []):
            if choch["timestamp"] >= ts:     continue
            if choch["id"] in triggered_ids: continue

            direction = "long" if choch["type"] == "bullish" else "short"
            triggered_ids.add(choch["id"])
            return {"direction": direction,
                    "entry_price": float(bar.get("close", 0)),
                    "setup_id": choch["id"],
                    "notes": f"CHoCH {choch['type']} continuation entry"}
        return None


class OBFVGConfluentStrategy(BaseStrategy):
    """
    Advanced: Enter only when an Order Block and an FVG overlap at the same price zone.
    Confluent zones have much higher probability than either alone.
    """
    name        = "ob_fvg_confluent"
    description = "Enter only when an Order Block and an FVG overlap (confluent zone). Higher probability than either alone."
    valid_sessions = ["london", "newyork", "overlap"]
    min_bars    = 80

    def find_signal(self, bars, i, smc, triggered_ids):
        bar  = bars[i]
        ts   = int(bar.get("timestamp", 0))
        high = float(bar.get("high", 0))
        low  = float(bar.get("low", 0))
        close= float(bar.get("close", 0))

        fvgs = [f for f in smc.get("fvg", [])
                if f["time2"] < ts and not f["filled"] and f["id"] not in triggered_ids]
        obs  = [o for o in smc.get("order_blocks", [])
                if o["timestamp"] < ts and o["id"] not in triggered_ids]

        for fvg in fvgs:
            fh, fl = fvg["high"], fvg["low"]
            for ob in obs:
                oh, ol = ob["high"], ob["low"]
                # Check overlap: both must be same direction and price zones must intersect
                if fvg["type"] != ob["type"]: continue
                overlap_hi = min(fh, oh)
                overlap_lo = max(fl, ol)
                if overlap_hi <= overlap_lo: continue  # no overlap

                # Price enters the confluent zone
                if fvg["type"] == "bullish" and low <= overlap_hi and close >= overlap_lo:
                    triggered_ids.add(fvg["id"]); triggered_ids.add(ob["id"])
                    return {"direction": "long",
                            "entry_price": overlap_hi,
                            "setup_id": f"conf_{fvg['id']}_{ob['id']}",
                            "notes": f"Confluent bullish OB+FVG zone {overlap_lo:.2f}-{overlap_hi:.2f}"}
                if fvg["type"] == "bearish" and high >= overlap_lo and close <= overlap_hi:
                    triggered_ids.add(fvg["id"]); triggered_ids.add(ob["id"])
                    return {"direction": "short",
                            "entry_price": overlap_lo,
                            "setup_id": f"conf_{fvg['id']}_{ob['id']}",
                            "notes": f"Confluent bearish OB+FVG zone {overlap_lo:.2f}-{overlap_hi:.2f}"}
        return None


class LiquiditySweepReversal(BaseStrategy):
    """
    Liquidity sweep then reversal: price sweeps above equal highs (buy stops)
    then closes back below — enter short in the direction of the reversal.
    Classic stop-hunt pattern.
    """
    name        = "liquidity_sweep_reversal"
    description = "Enter after a liquidity sweep (stop hunt): price spikes above/below a liquidity pool then closes back — reversal entry."
    valid_sessions = ["london", "newyork", "overlap"]
    min_bars    = 40

    def find_signal(self, bars, i, smc, triggered_ids):
        if i < 2: return None
        bar  = bars[i]
        prev = bars[i - 1]
        ts   = int(bar.get("timestamp", 0))
        close= float(bar.get("close", 0))
        prev_high = float(prev.get("high", 0))
        prev_low  = float(prev.get("low", 0))
        prev_close= float(prev.get("close", 0))

        for liq in smc.get("liquidity", []):
            if liq.get("timestamp", 0) >= ts: continue
            if liq["id"] in triggered_ids:    continue

            lvl = float(liq.get("price", liq.get("level", 0)))

            # Sweep of buy-side liquidity (equal highs) then close back below
            if liq.get("type") == "high":
                if prev_high > lvl and prev_close < lvl:
                    triggered_ids.add(liq["id"])
                    return {"direction": "short",
                            "entry_price": close,
                            "setup_id": liq["id"],
                            "notes": f"Buy-side liquidity sweep at {lvl:.2f}, reversal short"}

            # Sweep of sell-side liquidity (equal lows) then close back above
            if liq.get("type") == "low":
                if prev_low < lvl and prev_close > lvl:
                    triggered_ids.add(liq["id"])
                    return {"direction": "long",
                            "entry_price": close,
                            "setup_id": liq["id"],
                            "notes": f"Sell-side liquidity sweep at {lvl:.2f}, reversal long"}
        return None


class KillzoneOBEntry(BaseStrategy):
    """
    London or NY killzone open + OB: only enter during the first 2 hours
    of London (07:00-09:00 UTC) or NY (12:00-14:00 UTC) session.
    These are ICT's highest-probability entry windows.
    """
    name        = "killzone_ob_entry"
    description = "Order Block entry restricted to ICT killzones only: London open (07-09 UTC) and NY open (12-14 UTC). Filters out low-probability OB touches."
    valid_sessions = ["london", "newyork"]
    min_bars    = 50

    def find_signal(self, bars, i, smc, triggered_ids):
        from datetime import datetime
        bar = bars[i]
        ts  = int(bar.get("timestamp", 0))
        dt  = datetime.utcfromtimestamp(ts)
        hour= dt.hour

        # London killzone: 07-09 UTC | NY killzone: 12-14 UTC
        in_killzone = (7 <= hour < 9) or (12 <= hour < 14)
        if not in_killzone:
            return None

        high = float(bar.get("high", 0))
        low  = float(bar.get("low", 0))
        close= float(bar.get("close", 0))

        for ob in smc.get("order_blocks", []):
            if ob["timestamp"] >= ts:     continue
            if ob["id"] in triggered_ids: continue

            oh, ol = ob["high"], ob["low"]
            if ob["type"] == "bullish" and low <= oh and close >= ol:
                triggered_ids.add(ob["id"])
                return {"direction": "long", "entry_price": oh,
                        "setup_id": ob["id"],
                        "notes": f"Killzone OB entry (hour {hour} UTC)"}
            if ob["type"] == "bearish" and high >= ol and close <= oh:
                triggered_ids.add(ob["id"])
                return {"direction": "short", "entry_price": ol,
                        "setup_id": ob["id"],
                        "notes": f"Killzone OB entry (hour {hour} UTC)"}
        return None


# Registry: all built-in strategies
BUILTIN_STRATEGIES = {
    s.name: s for s in [
        FVGFillStrategy,
        OBReactionStrategy,
        BOSRetestStrategy,
        CHoCHConfirmStrategy,
        OBFVGConfluentStrategy,
        LiquiditySweepReversal,
        KillzoneOBEntry,
    ]
}
