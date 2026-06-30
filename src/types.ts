export type TrustStage = 'hypothesis' | 'backtest' | 'paper' | 'live_candidate' | 'live';

export interface SystemStatus {
  ollama: 'connected' | 'disconnected' | 'error';
  hermesRpc: 'connected' | 'disconnected' | 'error';
  mt5Zmq: {
    data: 'connected' | 'disconnected' | 'error';
    draw: 'connected' | 'disconnected' | 'error';
    order: 'connected' | 'disconnected' | 'error';
  };
  redis: 'connected' | 'disconnected' | 'error';
  chromaDb: 'connected' | 'disconnected' | 'error';
  obsidian: 'connected' | 'disconnected' | 'error';
}

export interface Trade {
  id: string;
  timestamp: string;
  instrument: 'XAUUSD';
  direction: 'BUY' | 'SELL';
  type: string; // SMC/ICT Setup Type: e.g. "Order Block Tap", "FVG Retest", "Liquidity Sweep"
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
  lotSize: number;
  currentPrice: number;
  pnl: number;
  status: 'OPEN' | 'CLOSED' | 'CANCELLED';
  stage: TrustStage;
  riskPercent: number; // Max 1%
  rrRatio: number;
  notes?: string;
  exitPrice?: number;
  closedAt?: string;
}

export interface FVG {
  id: string;
  timestamp: string;
  type: 'BULLISH' | 'BEARISH';
  high: number;
  low: number;
  midPoint: number;
  status: 'ACTIVE' | 'MITIGATED';
  mitigatedAt?: string;
}

export interface OrderBlock {
  id: string;
  timestamp: string;
  direction: 'BULLISH' | 'BEARISH';
  top: number;
  bottom: number;
  volume: number;
  status: 'ACTIVE' | 'TAPPED';
}

export interface LiquidityPool {
  id: string;
  type: 'BSL' | 'SSL'; // Buy Stop Liquidity, Sell Stop Liquidity
  price: number;
  timestamp: string;
  swept: boolean;
  sweptAt?: string;
}

export interface MarketMetrics {
  currentPrice: number;
  dailyHigh: number;
  dailyLow: number;
  sessions: {
    asian: { open: boolean; range: string };
    london: { open: boolean; range: string };
    newYork: { open: boolean; range: string };
  };
  fairValueGaps: FVG[];
  orderBlocks: OrderBlock[];
  liquidityPools: LiquidityPool[];
}

export interface LogMessage {
  id: string;
  timestamp: string;
  source: 'REDIS' | 'RPC' | 'OLLAMA' | 'MT5_DATA' | 'MT5_ORDER' | 'SYSTEM' | 'CHROMA';
  level: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS';
  text: string;
}

export interface ObsidianNote {
  path: string;
  title: string;
  content: string;
  folder: 'Strategy Cards' | 'Trade Logs' | 'Market Studies' | 'Hypotheses';
  tags: string[];
  mtime: string;
}

export interface ChromaDocument {
  id: string;
  text: string;
  metadata: {
    source: string;
    stage?: string;
    timestamp?: string;
    topic?: string;
  };
  distance?: number;
}

export interface StrategyCard {
  id: string;
  title: string;
  instrument: 'XAUUSD';
  stage: TrustStage;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  rules: string[];
  riskModel: {
    maxRisk: number; // 0.01 max
    maxDailyDD: number; // 0.04 max
    maxWeeklyDD: number; // 0.08 max
  };
  description: string;
}

export interface SkillCard {
  name: string;
  code: string;
  description: string;
  successRate: number;
  usageCount: number;
  lastUpdated: string;
}

export interface TerminalLine {
  id: string;
  timestamp: string;
  type: 'input' | 'output' | 'error' | 'success' | 'tool-call';
  text: string;
  toolDetails?: {
    name: string;
    args: string;
    result: string;
  };
}
