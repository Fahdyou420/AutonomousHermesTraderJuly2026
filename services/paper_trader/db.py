import os
import sqlite3
import time
from typing import List, Dict, Any, Optional

DB_DIR = "/data/trades"
DB_PATH = f"{DB_DIR}/paper_trades.db"

class PaperTradeDB:
    def __init__(self):
        # Create database directories
        os.makedirs(DB_DIR, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes tables and performs necessary migration setup."""
        with self._get_conn() as conn:
            # Create positions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id TEXT PRIMARY KEY,
                    signal_id TEXT,
                    instrument TEXT,
                    direction TEXT,
                    entry_price REAL,
                    sl REAL,
                    tp REAL,
                    lots REAL,
                    strategy_id TEXT,
                    setup_type TEXT,
                    session TEXT,
                    open_time INTEGER,
                    status TEXT,
                    close_price REAL,
                    close_time INTEGER,
                    pnl_r REAL,
                    close_reason TEXT
                )
            """)
            
            # Create stats_cache table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stats_cache (
                    id TEXT PRIMARY KEY,
                    computed_at INTEGER,
                    total_trades INTEGER,
                    win_rate REAL,
                    expectancy_r REAL,
                    max_dd_pct REAL,
                    profit_factor REAL,
                    avg_win_r REAL,
                    avg_loss_r REAL
                )
            """)
            conn.commit()

    def open_position(self, signal: Dict[str, Any]) -> str:
        """
        Inserts an open paper position into SQLite.
        """
        pos_id = signal.get("signal_id") or f"pos_{int(time.time())}_{signal.get('instrument')}"
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO positions (
                    id, signal_id, instrument, direction, entry_price, sl, tp, lots,
                    strategy_id, setup_type, session, open_time, status,
                    close_price, close_time, pnl_r, close_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pos_id,
                signal.get("signal_id"),
                signal.get("instrument"),
                signal.get("direction"),
                float(signal.get("entry_price", 0.0)),
                float(signal.get("sl", 0.0)),
                float(signal.get("tp", 0.0)),
                float(signal.get("lots", 0.1)),
                signal.get("strategy_id"),
                signal.get("setup_type"),
                signal.get("session"),
                int(signal.get("timestamp") or time.time()),
                "open",
                0.0, # close_price
                0,   # close_time
                0.0, # pnl_r
                ""   # close_reason
            ))
            conn.commit()
        return pos_id

    def close_position(self, pos_id: str, close_price: float, reason: str, close_time: Optional[int] = None) -> bool:
        """
        Closes an active position, computes final R ratio PnL, and updates DB.
        """
        if close_time is None:
            close_time = int(time.time())
            
        with self._get_conn() as conn:
            # First, fetch the opening details
            cur = conn.cursor()
            cur.execute("SELECT direction, entry_price, sl, tp FROM positions WHERE id = ?", (pos_id,))
            row = cur.fetchone()
            if not row:
                return False
                
            direction = row["direction"]
            entry_price = float(row["entry_price"])
            sl = float(row["sl"])
            
            # Compute PnL in terms of 'R'
            pnl_r = 0.0
            if direction.lower() in ["long", "buy"]:
                risk_distance = entry_price - sl
                if risk_distance > 0:
                    pnl_r = (close_price - entry_price) / risk_distance
            else: # short or sell
                risk_distance = sl - entry_price
                if risk_distance > 0:
                    pnl_r = (entry_price - close_price) / risk_distance
                    
            # Update position record
            conn.execute("""
                UPDATE positions
                SET status = 'closed',
                    close_price = ?,
                    close_time = ?,
                    pnl_r = ?,
                    close_reason = ?
                WHERE id = ?
            """, (close_price, close_time, pnl_r, reason, pos_id))
            conn.commit()
            
        # Recalculate stats cache asynchronously upon close
        self.compute_stats()
        return True

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Fetches all currently active open paper positions.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM positions WHERE status = 'open'")
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_history(self, n: int = 100) -> List[Dict[str, Any]]:
        """
        Fetches last 'n' closed paper trades.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM positions 
                WHERE status = 'closed' 
                ORDER BY close_time DESC 
                LIMIT ?
            """, (n,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def compute_stats(self) -> Dict[str, Any]:
        """
        Aggregates all closed historical trades and writes performance summary cache.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM positions WHERE status = 'closed' ORDER BY close_time ASC")
            trades = [dict(r) for r in cur.fetchall()]
            
        if not trades:
            empty_stats = {
                "total_trades": 0,
                "win_rate": 0.0,
                "expectancy_r": 0.0,
                "max_dd_pct": 0.0,
                "profit_factor": 1.0,
                "avg_win_r": 0.0,
                "avg_loss_r": 0.0
            }
            self._save_stats(empty_stats)
            return empty_stats
            
        total_trades = len(trades)
        wins = [t for t in trades if t["pnl_r"] > 0]
        losses = [t for t in trades if t["pnl_r"] <= 0]
        
        num_wins = len(wins)
        win_rate = (num_wins / total_trades) * 100.0
        
        avg_win_r = (sum(t["pnl_r"] for t in wins) / num_wins) if num_wins > 0 else 0.0
        avg_loss_r = (sum(abs(t["pnl_r"]) for t in losses) / len(losses)) if losses else 0.0
        
        # Expectancy formula in R multiple
        expectancy_r = (win_rate / 100.0) * avg_win_r - ((100.0 - win_rate) / 100.0) * avg_loss_r
        
        # Profit Factor
        gross_profits = sum(t["pnl_r"] for t in wins)
        gross_losses = sum(abs(t["pnl_r"]) for t in losses)
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else (gross_profits if gross_profits > 0 else 1.0)
        
        # Max Drawdown calculation using running cumulative R multiples
        running_equity = 100.0 # start at nominal 100 R baseline
        peak = running_equity
        max_dd = 0.0
        
        for t in trades:
            # Treat 1R as nominal 1% change for baseline drawdown modeling
            running_equity += t["pnl_r"]
            if running_equity > peak:
                peak = running_equity
            dd = (peak - running_equity) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
                
        stats = {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "expectancy_r": round(expectancy_r, 2),
            "max_dd_pct": round(max_dd, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win_r": round(avg_win_r, 2),
            "avg_loss_r": round(avg_loss_r, 2)
        }
        
        self._save_stats(stats)
        return stats

    def _save_stats(self, stats: Dict[str, Any]):
        """Persists the aggregated statistics inside the stats_cache table."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM stats_cache")
            conn.execute("""
                INSERT INTO stats_cache (
                    id, computed_at, total_trades, win_rate, expectancy_r, 
                    max_dd_pct, profit_factor, avg_win_r, avg_loss_r
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "latest",
                int(time.time()),
                stats["total_trades"],
                stats["win_rate"],
                stats["expectancy_r"],
                stats["max_dd_pct"],
                stats["profit_factor"],
                stats["avg_win_r"],
                stats["avg_loss_r"]
            ))
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """
        Retrieves current statistics. Recalculates if empty.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM stats_cache WHERE id = 'latest'")
            row = cur.fetchone()
            
        if row:
            return dict(row)
        else:
            return self.compute_stats()

    def get_strategy_performance(self) -> List[Dict[str, Any]]:
        """
        Aggregates performance by strategy_id.
        Important for finding promotion candidates.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            # Select closed trades grouped by strategy_id
            cur.execute("""
                SELECT strategy_id, 
                       COUNT(*) as total_trades,
                       SUM(CASE WHEN pnl_r > 0 THEN 1 ELSE 0 END) as wins,
                       SUM(pnl_r) as total_r
                FROM positions
                WHERE status = 'closed'
                GROUP BY strategy_id
            """)
            rows = cur.fetchall()
            
            perf_list = []
            for r in rows:
                sid = r["strategy_id"]
                tot = r["total_trades"]
                wns = r["wins"]
                tot_r = r["total_r"]
                
                win_rate = (wns / tot) if tot > 0 else 0.0
                
                # Fetch detailed rows for this strategy to calculate Drawdown and Expectancy
                cur.execute("""
                    SELECT pnl_r FROM positions 
                    WHERE status = 'closed' AND strategy_id = ? 
                    ORDER BY close_time ASC
                """, (sid,))
                pnl_rows = [row["pnl_r"] for row in cur.fetchall()]
                
                # Running drawdown calculation for strategy
                running_eq = 100.0
                peak = running_eq
                st_dd = 0.0
                st_wins = [p for p in pnl_rows if p > 0]
                st_losses = [p for p in pnl_rows if p <= 0]
                
                for pnl_val in pnl_rows:
                    running_eq += pnl_val
                    if running_eq > peak:
                        peak = running_eq
                    dd = (peak - running_eq) / peak * 100.0
                    if dd > st_dd:
                        st_dd = dd
                        
                avg_win = (sum(st_wins) / len(st_wins)) if st_wins else 0.0
                avg_loss = (sum(abs(p) for p in st_losses) / len(st_losses)) if st_losses else 0.0
                expectancy = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss)
                profit_factor = sum(st_wins) / sum(abs(p) for p in st_losses) if sum(abs(p) for p in st_losses) > 0 else (sum(st_wins) if st_wins else 1.0)
                
                perf_list.append({
                    "strategy_id": sid,
                    "total_trades": tot,
                    "win_rate": float(round(win_rate, 4)), # keeping fractional ratio
                    "expectancy_r": float(round(expectancy, 4)),
                    "max_dd_pct": float(round(st_dd, 2)),
                    "profit_factor": float(round(profit_factor, 2)),
                    "avg_win_r": float(round(avg_win, 4)),
                    "avg_loss_r": float(round(avg_loss, 4))
                })
                
            return perf_list
