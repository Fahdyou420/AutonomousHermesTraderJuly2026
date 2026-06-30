import uuid
from typing import List, Dict, Any, Tuple, Optional
from services.preprocessor import indicators

def detect_fvg(bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identifies Fair Value Gaps (FVG) within a 3-candle sequence.
    Bullish FVG: Low of candle 3 is greater than High of candle 1.
    Bearish FVG: High of candle 3 is lower than Low of candle 1.
    Includes active tracking to check if subsequent price action has filled the gap.
    """
    fvgs = []
    if len(bars) < 3:
        return fvgs
        
    for i in range(len(bars) - 2):
        b0 = bars[i]
        b1 = bars[i + 1]
        b2 = bars[i + 2]
        
        b0_high = float(b0.get("high", 0.0))
        b0_low = float(b0.get("low", 0.0))
        b2_high = float(b2.get("high", 0.0))
        b2_low = float(b2.get("low", 0.0))
        
        # Bullish FVG
        if b2_low > b0_high:
            fvg_id = f"fvg_bull_{i}_{int(b1.get('timestamp', 0))}"
            # Track if filled by subsequent candle closes
            filled = False
            for j in range(i + 3, len(bars)):
                bj_low = float(bars[j].get("low", 0.0))
                if bj_low <= b0_high:
                    filled = True
                    break
            
            fvgs.append({
                "id": fvg_id,
                "type": "bullish",
                "high": b2_low,
                "low": b0_high,
                "time1": int(b0.get("timestamp", 0)),
                "time2": int(b2.get("timestamp", 0)),
                "filled": filled
            })
            
        # Bearish FVG
        elif b2_high < b0_low:
            fvg_id = f"fvg_bear_{i}_{int(b1.get('timestamp', 0))}"
            # Track if filled by subsequent candles
            filled = False
            for j in range(i + 3, len(bars)):
                bj_high = float(bars[j].get("high", 0.0))
                if bj_high >= b0_low:
                    filled = True
                    break
                    
            fvgs.append({
                "id": fvg_id,
                "type": "bearish",
                "high": b0_low,
                "low": b2_high,
                "time1": int(b0.get("timestamp", 0)),
                "time2": int(b2.get("timestamp", 0)),
                "filled": filled
            })
            
    return fvgs

def detect_order_blocks(bars: List[Dict[str, Any]], swing_pts_high: List[Dict[str, Any]], swing_pts_low: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identifies Order Blocks (OB).
    Bullish OB: Highlight the last bearish close candle immediately before a swing low point.
    Bearish OB: Highlight the last bullish close candle immediately before a swing high point.
    """
    order_blocks = []
    
    # Track low swing point contexts
    for sl in swing_pts_low:
        idx = sl["index"]
        # Look backwards to find the nearest bearish candle
        for search_idx in range(idx, max(-1, idx - 5), -1):
            bar = bars[search_idx]
            close = float(bar.get("close", 0.0))
            op = float(bar.get("open", 0.0))
            
            # Bearish candle (Down-close) immediately prior/at the swing point
            if close < op:
                ob_id = f"ob_bull_{search_idx}_{int(bar.get('timestamp', 0))}"
                order_blocks.append({
                    "id": ob_id,
                    "type": "bullish",
                    "open": op,
                    "high": float(bar.get("high", 0.0)),
                    "low": float(bar.get("low", 0.0)),
                    "close": close,
                    "timestamp": int(bar.get("timestamp", 0))
                })
                break # only register the closest one
                
    # Track high swing point contexts
    for sh in swing_pts_high:
        idx = sh["index"]
        # Look backwards to find the nearest bullish candle
        for search_idx in range(idx, max(-1, idx - 5), -1):
            bar = bars[search_idx]
            close = float(bar.get("close", 0.0))
            op = float(bar.get("open", 0.0))
            
            # Bullish candle (Up-close) immediately prior/at the swing point
            if close > op:
                ob_id = f"ob_bear_{search_idx}_{int(bar.get('timestamp', 0))}"
                order_blocks.append({
                    "id": ob_id,
                    "type": "bearish",
                    "open": op,
                    "high": float(bar.get("high", 0.0)),
                    "low": float(bar.get("low", 0.0)),
                    "close": close,
                    "timestamp": int(bar.get("timestamp", 0))
                })
                break # only register the closest one
                
    return order_blocks

def detect_bos_and_choch(
    bars: List[Dict[str, Any]], 
    swing_highs_list: List[Dict[str, Any]], 
    swing_lows_list: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Simultaneously tracks trend breaks chronologically to output:
    - Break of Structure (BOS) -> Continuation of current trend
    - Change of Character (CHoCH) -> Reversal / First break of opposite structure
    """
    bos_list = []
    choch_list = []
    
    if not bars:
        return [], []
        
    # Maps of high and low values by index for fast chronologic lookup
    high_lookup = {sh["index"]: sh["price"] for sh in swing_highs_list}
    low_lookup = {sl["index"]: sl["price"] for sl in swing_lows_list}
    
    active_high: Optional[float] = None
    active_high_ts: Optional[int] = None
    active_low: Optional[float] = None
    active_low_ts: Optional[int] = None
    
    # Start with a neutral market structure bias
    current_bias = "neutral" # bullish, bearish, neutral
    
    # Walk through the bars chronologically
    for i, bar in enumerate(bars):
        close_price = float(bar.get("close", 0.0))
        ts = int(bar.get("timestamp", 0))
        
        # Keep updating last formed swing points
        if i in high_lookup:
            active_high = high_lookup[i]
            active_high_ts = ts
        if i in low_lookup:
            active_low = low_lookup[i]
            active_low_ts = ts
            
        # Check Bullish Structure Break (Price closes above active swing high)
        if active_high is not None and close_price > active_high:
            # We cracked a previous structural High!
            if current_bias == "bearish":
                # First sign of trend flip -> CHoCH
                choch_list.append({
                    "id": f"choch_bull_{i}_{ts}",
                    "type": "bullish",
                    "level": active_high,
                    "timestamp": ts
                })
                current_bias = "bullish"
            elif current_bias == "bullish":
                # Continuation break -> BOS
                bos_list.append({
                    "id": f"bos_bull_{i}_{ts}",
                    "type": "bullish",
                    "level": active_high,
                    "timestamp": ts
                })
            else:
                # neutral baseline initialized
                choch_list.append({
                    "id": f"choch_bull_{i}_{ts}",
                    "type": "bullish",
                    "level": active_high,
                    "timestamp": ts
                })
                current_bias = "bullish"
                
            # Once broken, reset active high to avoid repeated hits from same candle run
            active_high = None
            
        # Check Bearish Structure Break (Price closes below active swing low)
        elif active_low is not None and close_price < active_low:
            # We cracked a previous structural Low!
            if current_bias == "bullish":
                # First sign of trend flip -> CHoCH
                choch_list.append({
                    "id": f"choch_bear_{i}_{ts}",
                    "type": "bearish",
                    "level": active_low,
                    "timestamp": ts
                })
                current_bias = "bearish"
            elif current_bias == "bearish":
                # Continuation break -> BOS
                bos_list.append({
                    "id": f"bos_bear_{i}_{ts}",
                    "type": "bearish",
                    "level": active_low,
                    "timestamp": ts
                })
            else:
                # neutral baseline initialized
                choch_list.append({
                    "id": f"choch_bear_{i}_{ts}",
                    "type": "bearish",
                    "level": active_low,
                    "timestamp": ts
                })
                current_bias = "bearish"
                
            # Once broken, reset active low
            active_low = None
            
    return bos_list, choch_list

def detect_liquidity(
    swing_highs_list: List[Dict[str, Any]], 
    swing_lows_list: List[Dict[str, Any]], 
    tolerance_pips: float = 3.0
) -> List[Dict[str, Any]]:
    """
    Identifies equal highs (buy_side liquidity pools) and equal lows (sell_side liquidity pools).
    Uses a standard pip classification for Gold: 1 pip = 0.1 USD.
    Thus tolerance of 3 pips matches exactly 0.30 absolute gold range.
    """
    liquidity_pools = []
    
    # 3 pips tolerance on spot Gold = 0.30 difference
    tolerance_val = tolerance_pips * 0.1
    
    # Match Buy Side Liquidity (EQL swing highs)
    matched_highs = set()
    for i, sh1 in enumerate(swing_highs_list):
        if i in matched_highs:
            continue
        pool_highs = [sh1]
        for j in range(i + 1, len(swing_highs_list)):
            if j in matched_highs:
                continue
            sh2 = swing_highs_list[j]
            if abs(sh1["price"] - sh2["price"]) <= tolerance_val:
                pool_highs.append(sh2)
                matched_highs.add(j)
                
        if len(pool_highs) >= 2:
            matched_highs.add(i)
            avg_price = sum(h["price"] for h in pool_highs) / len(pool_highs)
            liquidity_pools.append({
                "id": f"liq_buyside_{int(avg_price)}_{sh1['timestamp']}",
                "type": "buy_side",
                "price": avg_price,
                "timestamps": [h["timestamp"] for h in pool_highs]
            })
            
    # Match Sell Side Liquidity (EQL swing lows)
    matched_lows = set()
    for i, sl1 in enumerate(swing_lows_list):
        if i in matched_lows:
            continue
        pool_lows = [sl1]
        for j in range(i + 1, len(swing_lows_list)):
            if j in matched_lows:
                continue
            sl2 = swing_lows_list[j]
            if abs(sl1["price"] - sl2["price"]) <= tolerance_val:
                pool_lows.append(sl2)
                matched_lows.add(j)
                
        if len(pool_lows) >= 2:
            matched_lows.add(i)
            avg_price = sum(l["price"] for l in pool_lows) / len(pool_lows)
            liquidity_pools.append({
                "id": f"liq_sellside_{int(avg_price)}_{sl1['timestamp']}",
                "type": "sell_side",
                "price": avg_price,
                "timestamps": [l["timestamp"] for l in pool_lows]
            })
            
    return liquidity_pools

def analyse_structure(bars: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Runs complete SMC structure sweeps over passed dataset.
    """
    if not bars:
        return {
            "fvg": [],
            "order_blocks": [],
            "bos": [],
            "choch": [],
            "liquidity": [],
            "swing_highs": [],
            "swing_lows": []
        }
        
    # Calculate Swing extremes (Fractal lookback=5 is rule baseline)
    shs = indicators.swing_highs(bars, lookback=5)
    sls = indicators.swing_lows(bars, lookback=5)
    
    # Structure analyses
    fvgs = detect_fvg(bars)
    obs = detect_order_blocks(bars, shs, sls)
    bos, choch = detect_bos_and_choch(bars, shs, sls)
    liq = detect_liquidity(shs, sls, tolerance_pips=3.0)
    
    return {
        "fvg": fvgs,
        "order_blocks": obs,
        "bos": bos,
        "choch": choch,
        "liquidity": liq,
        "swing_highs": shs,
        "swing_lows": sls
    }
