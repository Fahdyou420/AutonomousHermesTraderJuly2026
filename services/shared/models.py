import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

@dataclass
class MarketBar:
    instrument: str
    timeframe: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    spread: int
    session: str
    chunk_id: int
    total_chunks: int
    bar_type: str = "bar"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketBar':
        return cls(
            instrument=data.get("instrument", ""),
            timeframe=data.get("timeframe", ""),
            timestamp=int(data.get("timestamp", 0)),
            open=float(data.get("open", 0.0)),
            high=float(data.get("high", 0.0)),
            low=float(data.get("low", 0.0)),
            close=float(data.get("close", 0.0)),
            volume=float(data.get("volume", 0.0)),
            spread=int(data.get("spread", 0)),
            session=data.get("session", ""),
            chunk_id=int(data.get("chunk_id", 0)),
            total_chunks=int(data.get("total_chunks", 0)),
            bar_type=data.get("bar_type", "bar")
        )

@dataclass
class TradeSignal:
    signal_id: str
    timestamp: int
    instrument: str
    direction: str  # long/short or buy/sell
    entry_price: float
    entry_type: str  # market/limit
    sl: float
    tp: float
    lots: float
    timeframe: str
    strategy_id: str
    setup_type: str
    session: str
    mode: str  # paper/live
    r_ratio: float
    confidence: str  # high/medium/low
    agent_notes: str
    status: str  # pending/approved/rejected

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeSignal':
        return cls(
            signal_id=data.get("signal_id", "") or str(uuid.uuid4()),
            timestamp=int(data.get("timestamp", 0)),
            instrument=data.get("instrument", ""),
            direction=data.get("direction", ""),
            entry_price=float(data.get("entry_price", 0.0)),
            entry_type=data.get("entry_type", "market"),
            sl=float(data.get("sl", 0.0)),
            tp=float(data.get("tp", 0.0)),
            lots=float(data.get("lots", 0.0)),
            timeframe=data.get("timeframe", ""),
            strategy_id=data.get("strategy_id", ""),
            setup_type=data.get("setup_type", ""),
            session=data.get("session", ""),
            mode=data.get("mode", "paper"),
            r_ratio=float(data.get("r_ratio", 0.0)),
            confidence=data.get("confidence", "medium"),
            agent_notes=data.get("agent_notes", ""),
            status=data.get("status", "pending")
        )

@dataclass
class StrategyConfig:
    strategy_id: str
    name: str
    instrument: str
    timeframe: str
    session_filter: List[str]
    entry_logic: Dict[str, Any]
    sl_logic: Dict[str, Any]
    tp_logic: Dict[str, Any]
    risk_pct: float
    max_trades_per_day: int
    spread_gate_pips: int
    date_from: str
    date_to: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyConfig':
        return cls(
            strategy_id=data.get("strategy_id", ""),
            name=data.get("name", ""),
            instrument=data.get("instrument", ""),
            timeframe=data.get("timeframe", ""),
            session_filter=list(data.get("session_filter", [])),
            entry_logic=dict(data.get("entry_logic", {})),
            sl_logic=dict(data.get("sl_logic", {})),
            tp_logic=dict(data.get("tp_logic", {})),
            risk_pct=float(data.get("risk_pct", 1.0)),
            max_trades_per_day=int(data.get("max_trades_per_day", 1)),
            spread_gate_pips=int(data.get("spread_gate_pips", 25)),
            date_from=data.get("date_from", ""),
            date_to=data.get("date_to", "")
        )

@dataclass
class BacktestResult:
    strategy_id: str
    total_trades: int
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    expectancy_r: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    trades: List[Dict[str, Any]]
    equity_curve: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BacktestResult':
        return cls(
            strategy_id=data.get("strategy_id", ""),
            total_trades=int(data.get("total_trades", 0)),
            win_rate=float(data.get("win_rate", 0.0)),
            avg_win_r=float(data.get("avg_win_r", 0.0)),
            avg_loss_r=float(data.get("avg_loss_r", 0.0)),
            expectancy_r=float(data.get("expectancy_r", 0.0)),
            max_drawdown_pct=float(data.get("max_drawdown_pct", 0.0)),
            sharpe_ratio=float(data.get("sharpe_ratio", 0.0)),
            profit_factor=float(data.get("profit_factor", 0.0)),
            trades=list(data.get("trades", [])),
            equity_curve=list(data.get("equity_curve", []))
        )

@dataclass
class DrawCommand:
    cmd: str = "draw"
    type: str = ""  # fvg, ob, line, rect
    id: str = ""
    price1: float = 0.0
    price2: float = 0.0
    time1: int = 0
    time2: int = 0
    color: str = ""
    style: str = ""
    width: int = 1
    label: str = ""
    timeframe: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DrawCommand':
        return cls(
            cmd=data.get("cmd", "draw"),
            type=data.get("type", ""),
            id=data.get("id", ""),
            price1=float(data.get("price1", 0.0)),
            price2=float(data.get("price2", 0.0)),
            time1=int(data.get("time1", 0)),
            time2=int(data.get("time2", 0)),
            color=data.get("color", ""),
            style=data.get("style", ""),
            width=int(data.get("width", 1)),
            label=data.get("label", ""),
            timeframe=data.get("timeframe", "")
        )

@dataclass
class OrderCommand:
    cmd: str = "order"
    action: str = ""  # BUY, SELL, CLOSE, MODIFY
    instrument: str = ""
    lots: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""
    magic: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderCommand':
        return cls(
            cmd=data.get("cmd", "order"),
            action=data.get("action", ""),
            instrument=data.get("instrument", ""),
            lots=float(data.get("lots", 0.0)),
            sl=float(data.get("sl", 0.0)),
            tp=float(data.get("tp", 0.0)),
            comment=data.get("comment", ""),
            magic=int(data.get("magic", 0))
        )
