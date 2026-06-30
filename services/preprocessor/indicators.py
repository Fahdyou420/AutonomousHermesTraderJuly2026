import math
from datetime import datetime
from typing import List, Dict, Any

def get_session(timestamp_utc: int) -> str:
    """
    Classifies a UTC timestamp (seconds) into one of market sessions:
    Asian (00:00 - 08:00 UTC)
    London (08:00 - 16:00 UTC)
    New York (13:00 - 21:00 UTC)
    Overlap (London/NY overlap: 13:00 - 16:00 UTC)
    Off-hours (21:00 - 00:00 UTC)
    """
    dt = datetime.utcfromtimestamp(timestamp_utc)
    hour = dt.hour
    
    # Overlap London and New York
    if 13 <= hour < 16:
        return "overlap"
    # New York (13:00 to 21:00) excluding the overlap
    elif 16 <= hour < 21:
        return "newyork"
    # London (08:00 to 16:00) excluding the overlap
    elif 8 <= hour < 13:
        return "london"
    # Asian (00:00 to 08:00)
    elif 0 <= hour < 8:
        return "asian"
    else:
        return "off"

def ema(closes: List[float], period: int) -> List[float]:
    """
    Calculates Exponential Moving Average (EMA) for a list of close prices.
    Returns a list of the same length as closes.
    """
    if not closes:
        return []
    
    ema_list = [0.0] * len(closes)
    multiplier = 2.0 / (period + 1.0)
    
    # First value is simple SMA or the close price itself if elements < period
    if len(closes) < period:
        # Fallback to simple SMA
        val = sum(closes) / len(closes)
        return [val] * len(closes)
        
    initial_sma = sum(closes[:period]) / period
    ema_list[period - 1] = initial_sma
    
    # Pre-fill values prior to the first calculated EMA with simple SMA or closes
    for idx in range(period - 1):
        ema_list[idx] = sum(closes[:idx+1]) / (idx + 1)
        
    for i in range(period, len(closes)):
        ema_list[i] = (closes[i] - ema_list[i - 1]) * multiplier + ema_list[i - 1]
        
    return ema_list

def atr(bars: List[Dict[str, Any]], period: int = 14) -> List[float]:
    """
    Calculates Average True Range (ATR) over period.
    Returns a list of ATR values matching the bars length.
    """
    if not bars:
        return []
        
    tr_list = []
    for i, bar in enumerate(bars):
        high = float(bar.get("high", 0.0))
        low = float(bar.get("low", 0.0))
        if i == 0:
            tr_list.append(high - low)
        else:
            prev_close = float(bars[i - 1].get("close", 0.0))
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_list.append(tr)
            
    atr_list = [0.0] * len(bars)
    if len(tr_list) < period:
        # Fallback simple average
        avg_tr = sum(tr_list) / len(tr_list) if tr_list else 0.0
        return [avg_tr] * len(bars)
        
    # Initial ATR is simple average of first period TRs
    initial_atr = sum(tr_list[:period]) / period
    atr_list[period - 1] = initial_atr
    
    # Pre-fill prior items
    for idx in range(period - 1):
        atr_list[idx] = sum(tr_list[:idx+1]) / (idx+1) if tr_list else 0.0
        
    # Smoothed Wilder's Moving Average
    for i in range(period, len(bars)):
        atr_list[i] = (atr_list[i - 1] * (period - 1) + tr_list[i]) / period
        
    return atr_list

def swing_highs(bars: List[Dict[str, Any]], lookback: int = 5) -> List[Dict[str, Any]]:
    """
    Identifies fractal Swing High points.
    A bar high is a swing high if it is greater than the highs of previous 'lookback' bars
    and following 'lookback' bars.
    Returns list of {index, price, timestamp}.
    """
    swings = []
    for i in range(lookback, len(bars) - lookback):
        current_high = float(bars[i].get("high", 0.0))
        is_high = True
        for j in range(1, lookback + 1):
            if float(bars[i - j].get("high", 0.0)) >= current_high or float(bars[i + j].get("high", 0.0)) > current_high:
                is_high = False
                break
        if is_high:
            swings.append({
                "index": i,
                "price": current_high,
                "timestamp": int(bars[i].get("timestamp", 0))
            })
    return swings

def swing_lows(bars: List[Dict[str, Any]], lookback: int = 5) -> List[Dict[str, Any]]:
    """
    Identifies fractal Swing Low points.
    A bar low is a swing low if it is lesser than the lows of previous 'lookback' bars
    and following 'lookback' bars.
    Returns list of {index, price, timestamp}.
    """
    swings = []
    for i in range(lookback, len(bars) - lookback):
        current_low = float(bars[i].get("low", 0.0))
        is_low = True
        for j in range(1, lookback + 1):
            if float(bars[i - j].get("low", 0.0)) <= current_low or float(bars[i + j].get("low", 0.0)) < current_low:
                is_low = False
                break
        if is_low:
            swings.append({
                "index": i,
                "price": current_low,
                "timestamp": int(bars[i].get("timestamp", 0))
            })
    return swings

def enrich_bar(bar_dict: Dict[str, Any], all_bars: List[Dict[str, Any]], index: int) -> Dict[str, Any]:
    """
    Appends indicator statistics to individual bar dictionary.
    Assumes indicators have been globally pre-calculated to avoid performance degradation.
    """
    # Defensive check
    if not all_bars:
        return bar_dict
        
    # Verify indicator metrics are available in cache
    # First, calculate entire arrays to retrieve precise current index values
    closes = [float(b.get("close", 0.0)) for b in all_bars]
    
    # Precompute arrays for index targeting
    ema_20_arr = ema(closes, 20)
    ema_50_arr = ema(closes, 50)
    atr_14_arr = atr(all_bars, 14)
    
    # Calculate swings (standard lookback=5)
    sw_highs_indices = {s["index"] for s in swing_highs(all_bars, lookback=5)}
    sw_lows_indices = {s["index"] for s in swing_lows(all_bars, lookback=5)}
    
    # Fetch individual values
    target_idx = min(max(0, index), len(all_bars) - 1)
    
    # Add indicators to the copy target
    enriched = dict(bar_dict)
    enriched["atr14"] = atr_14_arr[target_idx]
    enriched["ema20"] = ema_20_arr[target_idx]
    enriched["ema50"] = ema_50_arr[target_idx]
    
    # Session routing
    ts = int(bar_dict.get("timestamp", 0))
    enriched["session"] = get_session(ts)
    
    # Spread ratio to filter trading during unstable hours
    spread_points = int(bar_dict.get("spread", 0))
    atr_val = atr_14_arr[target_idx]
    
    # Prevent divide by zero: convert spread (typically pips or points depending on instrument tick value)
    # Spot gold spreads are usually in points (e.g. 15 points = 1.5 pips). Let's calculate standard ratio
    if atr_val > 0:
        enriched["spread_atr_ratio"] = float(spread_points / (atr_val * 100)) # approximate points to ATR scaling
    else:
        enriched["spread_atr_ratio"] = 0.0
        
    enriched["is_swing_high"] = (target_idx in sw_highs_indices)
    enriched["is_swing_low"] = (target_idx in sw_lows_indices)
    
    return enriched
