import os
import sys
import uuid
import math
from datetime import datetime
from typing import List, Dict, Any, Optional

# Ensure correct python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.shared.models import StrategyConfig, BacktestResult
from services.preprocessor.smc_detector import analyse_structure
from services.preprocessor.indicators import atr

class BacktestEngine:
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.initial_equity = 10000.0
        self.running_equity = self.initial_equity
        self.peak_equity = self.initial_equity
        self.max_drawdown = 0.0
        self._strategy_instance = None  # cached plugin instance for this run
        
        # Max limit counters
        self.max_risk_pct = getattr(config, "risk_pct", 1.0)
        self.max_trades_per_day = getattr(config, "max_trades_per_day", 1)
        self.spread_gate_pips = getattr(config, "spread_gate_pips", 25)
        
    def _calculate_sl_tp(self, direction: str, entry_price: float, current_atr: float, bar: Dict[str, Any]) -> tuple:
        """
        Calculates SL and TP levels based on sl_logic and tp_logic configuration.
        """
        sl_config = self.config.sl_logic
        tp_config = self.config.tp_logic
        
        # Default pips configurations
        sl_type = sl_config.get("type", "fixed")
        sl_val = float(sl_config.get("value", 15.0))
        
        tp_type = tp_config.get("type", "fixed")
        tp_val = float(tp_config.get("value", 30.0))
        
        # Convert pips to Gold price change (1 pip = 0.1 USD)
        sl_dist = sl_val * 0.1
        tp_dist = tp_val * 0.1
        
        # Check ATR overrides
        if sl_type == "atr":
            mult = float(sl_config.get("multiplier", 1.5))
            sl_dist = max(0.1, current_atr * mult)
            
        if tp_type == "atr":
            mult = float(tp_config.get("multiplier", 3.0))
            tp_dist = max(0.2, current_atr * mult)
            
        # Structure-based offsets
        if sl_type == "structure_low" and direction == "long":
            sl_dist = abs(entry_price - float(bar.get("low", entry_price))) + 0.5
        elif sl_type == "structure_high" and direction == "short":
            sl_dist = abs(float(bar.get("high", entry_price)) - entry_price) + 0.5

        if direction == "long":
            sl = entry_price - sl_dist
            tp = entry_price + tp_dist
        else:
            sl = entry_price + sl_dist
            tp = entry_price - tp_dist
            
        return sl, tp

    def run(self, bars: List[Dict[str, Any]]) -> BacktestResult:
        if not bars:
            return BacktestResult(
                strategy_id=self.config.strategy_id,
                total_trades=0,
                win_rate=0.0,
                avg_win_r=0.0,
                avg_loss_r=0.0,
                expectancy_r=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                profit_factor=0.0,
                trades=[],
                equity_curve=[]
            )

        # 1. Run full SMC Analysis on all bars to build historic structures lookup
        smc_results = analyse_structure(bars)
        
        # Cache indicators indices for reference
        closes = [float(b.get("close", 0.0)) for b in bars]
        atr14_arr = atr(bars, 14)
        
        # Deconstruct analysis maps by symbol/timestamp for chronological alignment
        # This prevents look-ahead bias because we only evaluate structures formed till bar 'i'
        fvgs_list = smc_results.get("fvg", [])
        obs_list = smc_results.get("order_blocks", [])
        bos_list = smc_results.get("bos", [])
        choch_list = smc_results.get("choch", [])
        liquidity_list = smc_results.get("liquidity", [])
        
        # Track history structure states
        active_trades = []
        completed_trades = []
        
        # Track active/triggered structures to prevent repeating triggers on the exact same zones
        triggered_structure_ids = set()
        
        # Daily trades count cache: keyed by YYYY-MM-DD
        daily_trades_counter = {}
        
        # Equity tracing
        self.running_equity = self.initial_equity
        self.peak_equity = self.initial_equity
        self.max_drawdown = 0.0
        
        equity_curve_log = []
        
        # Group equity by trading day for annualized Sharpe
        daily_equity_log = {}
        
        # Walk chronologically through the data
        for i, bar in enumerate(bars):
            timestamp = int(bar.get("timestamp", 0))
            bar_date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
            
            # Record daily equity close value
            daily_equity_log[bar_date] = self.running_equity
            
            # --- PHASE A: UPDATE OPEN TRADES ---
            high = float(bar.get("high", 0.0))
            low = float(bar.get("low", 0.0))
            close = float(bar.get("close", 0.0))
            current_atr = atr14_arr[i]
            
            still_open = []
            for t in active_trades:
                # Check exit bounds
                direction = t["direction"]
                sl = t["sl"]
                tp = t["tp"]
                lots = t["lots"]
                entry_price = t["entry_price"]
                
                hit_sl = False
                hit_tp = False
                exit_price = 0.0
                
                if direction == "long":
                    # If both SL and TP hit on same bar (highly volatile candle), assume SL hit (conservative)
                    if low <= sl and high >= tp:
                        hit_sl = True
                        exit_price = sl
                    elif low <= sl:
                        hit_sl = True
                        exit_price = sl
                    elif high >= tp:
                        hit_tp = True
                        exit_price = tp
                else: # short
                    if high >= sl and low <= tp:
                        hit_sl = True
                        exit_price = sl
                    elif high >= sl:
                        hit_sl = True
                        exit_price = sl
                    elif low <= tp:
                        hit_tp = True
                        exit_price = tp
                        
                if hit_sl or hit_tp:
                    # Calculate contract PnL (Gold multiplier is 100)
                    if direction == "long":
                        pnl = (exit_price - entry_price) * lots * 100.0
                    else:
                        pnl = (entry_price - exit_price) * lots * 100.0
                        
                    t["exit_price"] = exit_price
                    t["exit_timestamp"] = timestamp
                    t["pnl"] = pnl
                    t["status"] = "closed"
                    t["result"] = "win" if hit_tp else "loss"
                    
                    # Update balance fields
                    self.running_equity += pnl
                    self.peak_equity = max(self.peak_equity, self.running_equity)
                    
                    # Log drawdown metric
                    dd = (self.peak_equity - self.running_equity) / self.peak_equity * 100.0
                    self.max_drawdown = max(self.max_drawdown, dd)
                    
                    completed_trades.append(t)
                else:
                    still_open.append(t)
                    
            active_trades = still_open
            
            # Log periodic equity
            equity_curve_log.append({
                "timestamp": timestamp,
                "equity": self.running_equity
            })
            
            # --- PHASE B: EVALUATE DAILY TRADE GATES ---
            # Parse session context
            current_session = bar.get("session", "overlap")
            session_filters = self.config.session_filter
            if session_filters and current_session not in session_filters:
                continue
                
            # Parse Spread Gate (MT5 spread is in broker points, e.g. 15 points = 1.5 pips)
            current_spread = int(bar.get("spread", 0))
            # Compare points directly to input spreads or scale by 10 (25 pips = 250 points)
            if current_spread > (self.spread_gate_pips * 10):
                continue
                
            # Trade block limit check
            today_count = daily_trades_counter.get(bar_date, 0)
            if today_count >= self.max_trades_per_day:
                continue
                
            # --- PHASE C: SCAN STRUCTURE TRIGGERS ---
            # Strategy is loaded dynamically via the plugin system.
            # Supports builtin strategies AND agent-created custom strategies.
            trigger_signal = None
            setup_type = self.config.entry_logic.get("type", "fvg_fill")

            if self._strategy_instance is None:
                from services.backtester.strategy_loader import load_strategy
                cls = load_strategy(setup_type)
                if cls is None:
                    continue  # unknown strategy type — skip bar
                self._strategy_instance = cls()

            strategy = self._strategy_instance

            # Session check delegated to plugin
            if strategy.valid_sessions and current_session not in strategy.valid_sessions:
                continue

            # Minimum bars guard
            if i < strategy.min_bars:
                continue

            trigger_signal = strategy.find_signal(
                bars, i, smc_results, triggered_structure_ids
            )
                    
            if trigger_signal:
                # Calculate SL and TP
                dir_val = trigger_signal["direction"]
                ep = trigger_signal["entry_price"]
                
                sl, tp = self._calculate_sl_tp(dir_val, ep, current_atr, bar)
                
                # Risk calculation logic
                risk_amt = self.running_equity * (self.max_risk_pct / 100.0)
                sl_distance_points = abs(ep - sl)
                
                if sl_distance_points > 0:
                    # Gold contract size coefficient = 100
                    lots = risk_amt / (sl_distance_points * 100.0)
                    lots = max(0.01, min(100.0, round(lots, 2))) # limit checks
                else:
                    lots = 0.1
                    
                # Create Trade representation
                trade = {
                    "trade_id": str(uuid.uuid4()),
                    "strategy_id": self.config.strategy_id,
                    "instrument": self.config.instrument,
                    "timeframe": self.config.timeframe,
                    "direction": dir_val,
                    "entry_price": ep,
                    "sl": sl,
                    "tp": tp,
                    "lots": lots,
                    "entry_timestamp": timestamp,
                    "exit_timestamp": 0,
                    "exit_price": 0.0,
                    "pnl": 0.0,
                    "setup_type": setup_type,
                    "session": current_session,
                    "status": "open",
                    "result": "pending",
                    "notes": trigger_signal["notes"]
                }
                
                active_trades.append(trade)
                daily_trades_counter[bar_date] = today_count + 1

        # Force liquidating remaining open trades at final close price of the test sequence
        if active_trades and bars:
            final_bar = bars[-1]
            final_close = float(final_bar.get("close", 0.0))
            final_ts = int(final_bar.get("timestamp", 0))
            
            for t in active_trades:
                direction = t["direction"]
                entry_price = t["entry_price"]
                lots = t["lots"]
                
                if direction == "long":
                    pnl = (final_close - entry_price) * lots * 100.0
                else:
                    pnl = (entry_price - final_close) * lots * 100.0
                    
                t["exit_price"] = final_close
                t["exit_timestamp"] = final_ts
                t["pnl"] = pnl
                t["status"] = "closed"
                t["result"] = "liquidate"
                
                self.running_equity += pnl
                completed_trades.append(t)
                
            active_trades = []

        # --- STATS SUMMARIZATION PERFORMANCE LOGIC ---
        total_trades = len(completed_trades)
        wins = [t for t in completed_trades if t["result"] == "win"]
        losses = [t for t in completed_trades if t["result"] in ["loss", "liquidate"]] # treat forced exit as loss for safety
        
        num_wins = len(wins)
        win_rate = (num_wins / total_trades * 100.0) if total_trades > 0 else 0.0
        
        # Calculate Expectancies based on theoretical R balances
        total_win_amt = sum(w["pnl"] for w in wins)
        total_loss_amt = abs(sum(l["pnl"] for l in losses))
        
        profit_factor = (total_win_amt / total_loss_amt) if total_loss_amt > 0 else (total_win_amt if total_win_amt > 0 else 1.0)
        
        # Win details scaling
        avg_win = (total_win_amt / num_wins) if num_wins > 0 else 0.0
        avg_loss = (total_loss_amt / len(losses)) if losses else 0.0
        
        avg_win_r = avg_win / 100.0 # simple scaling
        avg_loss_r = avg_loss / 100.0
        expectancy_r = (win_rate / 100.0) * avg_win_r - ((100.0 - win_rate) / 100.0) * avg_loss_r
        
        # Annualized Sharpe ratio calculation logic
        sharpe_ratio = self._calculate_sharpe(daily_equity_log)

        # Build clean chronological arrays
        return BacktestResult(
            strategy_id=self.config.strategy_id,
            total_trades=total_trades,
            win_rate=float(round(win_rate, 2)),
            avg_win_r=float(round(avg_win_r, 2)),
            avg_loss_r=float(round(avg_loss_r, 2)),
            expectancy_r=float(round(expectancy_r, 2)),
            max_drawdown_pct=float(round(self.max_drawdown, 2)),
            sharpe_ratio=float(round(sharpe_ratio, 2)),
            profit_factor=float(round(profit_factor, 2)),
            trades=completed_trades,
            equity_curve=equity_curve_log
        )

    def _calculate_sharpe(self, daily_balances: Dict[str, float]) -> float:
        """
        Computes the Sharpe Ratio using daily log returns.
        Standard annualized formula: sqrt(252) * (mean / std)
        """
        sorted_dates = sorted(daily_balances.keys())
        if len(sorted_dates) < 5:
            return 0.0
            
        returns = []
        for i in range(1, len(sorted_dates)):
            yest_bal = daily_balances[sorted_dates[i - 1]]
            tod_bal = daily_balances[sorted_dates[i]]
            if yest_bal > 0:
                ret = (tod_bal - yest_bal) / yest_bal
                returns.append(ret)
                
        if not returns:
            return 0.0
            
        mean_ret = sum(returns) / len(returns)
        
        # Calculate variance and std dev
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0.0
            
        # Annualize assuming 252 trading days per year
        sharpe = math.sqrt(252) * (mean_ret / std_dev)
        return sharpe
