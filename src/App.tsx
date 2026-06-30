import React, { useState, useEffect } from 'react';
import {
  SystemStatus,
  MarketMetrics,
  Trade,
  ObsidianNote,
  SkillCard,
  StrategyCard,
  TrustStage
} from './types';
import StatusCard from './components/StatusCard';
import AgentTerminal from './components/AgentTerminal';
import KnowledgeExplorer from './components/KnowledgeExplorer';
import StrategyStudio from './components/StrategyStudio';
import TradeMonitor from './components/TradeMonitor';
import AutonomousLoops from './components/AutonomousLoops';
import { Terminal, LineChart, Cpu, BookOpen, Settings2, Shield, Activity, RefreshCw } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'terminal' | 'trades' | 'strategies' | 'vault' | 'loops'>('terminal');
  
  // App states
  const [status, setStatus] = useState<SystemStatus>({
    ollama: 'disconnected',
    hermesRpc: 'disconnected',
    mt5Zmq: { data: 'disconnected', draw: 'disconnected', order: 'disconnected' },
    redis: 'disconnected',
    chromaDb: 'disconnected',
    obsidian: 'disconnected'
  });
  
  const [marketMetrics, setMarketMetrics] = useState<MarketMetrics>({
    currentPrice: 0.0,
    dailyHigh: 0.0,
    dailyLow: 0.0,
    sessions: {
      asian: { open: false, range: "" },
      london: { open: false, range: "" },
      newYork: { open: false, range: "" }
    },
    fairValueGaps: [],
    orderBlocks: [],
    liquidityPools: []
  });

  const [activeTrades, setActiveTrades] = useState<Trade[]>([]);
  const [closedTrades, setClosedTrades] = useState<Trade[]>([]);
  const [balance, setBalance] = useState<number>(0.0);
  const [equity, setEquity] = useState<number>(0.0);
  const [dailyDD, setDailyDD] = useState<number>(0);
  const [weeklyDD, setWeeklyDD] = useState<number>(0);
  
  const [logs, setLogs] = useState<any[]>([]);
  const [notes, setNotes] = useState<ObsidianNote[]>([]);
  const [skills, setSkills] = useState<SkillCard[]>([]);
  const [loops, setLoops] = useState<any>({
    nightlyMarketScan: { lastRun: '', status: 'IDLE', outcome: 'Idle' },
    skillAutoCreation: { lastRun: '', status: 'IDLE', outcome: 'Idle' },
    paperTradeReview: { lastRun: '', status: 'IDLE', outcome: 'Idle' },
    hypothesisRandD: { lastRun: '', status: 'IDLE', outcome: 'Idle' }
  });

  const [loading, setLoading] = useState(false);

  // Strategy Card states
  const [strategyCards, setStrategyCards] = useState<StrategyCard[]>([]);

  // Load backend telemetry data
  const fetchAllData = async () => {
    try {
      const [resStatus, resMarket, resTrades, resLogs, resVault, resSkills, resLoops, resStrategies] = await Promise.all([
        fetch('/api/status').then(r => r.json()),
        fetch('/api/market').then(r => r.json()),
        fetch('/api/trades').then(r => r.json()),
        fetch('/api/logs').then(r => r.json()),
        fetch('/api/vault').then(r => r.json()),
        fetch('/api/skills').then(r => r.json()),
        fetch('/api/loops').then(r => r.json()),
        fetch('/api/strategy/list').then(r => r.json()).catch(() => [])
      ]);

      setStatus(resStatus);
      setMarketMetrics({
        ...resMarket,
        currentPrice: resMarket.currentPrice || 0,
        dailyHigh: resMarket.dailyHigh || 0,
        dailyLow: resMarket.dailyLow || 0
      });
      
      setActiveTrades(resTrades.active || []);
      setClosedTrades(resTrades.closed || []);
      setBalance(resTrades.balance || 0);
      setEquity(resTrades.equity || 0);
      setDailyDD(resTrades.dailyDDPercent || 0);
      setWeeklyDD(resTrades.weeklyDDPercent || 0);

      setLogs(resLogs);
      setNotes(resVault);
      setSkills(resSkills);
      setLoops(resLoops);

      if (resStrategies && Array.isArray(resStrategies) && resStrategies.length > 0) {
        const mappedCards: StrategyCard[] = resStrategies.map((s: any) => ({
          id: s.id,
          title: s.name,
          instrument: s.instrument || 'XAUUSD',
          stage: s.status as TrustStage,
          winRate: s.rules?.metrics?.win_rate ? s.rules.metrics.win_rate * 100 : 0,
          profitFactor: s.rules?.metrics?.profit_factor || 0,
          totalTrades: s.rules?.metrics?.total_trades || 0,
          rules: Array.isArray(s.rules?.entry_rules) ? s.rules.entry_rules : [],
          riskModel: { maxRisk: 0.01, maxDailyDD: 0.04, maxWeeklyDD: 0.08 },
          description: s.content?.split('\n').slice(0, 3).join(' ') || s.name
        }));
        setStrategyCards(mappedCards);
      }

    } catch (err) {
      console.error("Failed to sync backend state:", err);
    }
  };

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleRefreshStatus = async () => {
    setLoading(true);
    await fetchAllData();
    setLoading(false);
  };

  const handlePlaceTrade = async (params: any) => {
    const res = await fetch('/api/trades', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || "Order execution pipeline broken.");
    }
    const data = await res.json();
    fetchAllData();
    return data;
  };

  const handleCloseTrade = async (id: string) => {
    const res = await fetch(`/api/trades/close/${id}`, {
      method: 'POST'
    });
    if (!res.ok) {
      throw new Error("Unable to clear position tickets.");
    }
    const data = await res.json();
    fetchAllData();
    return data;
  };

  const handleAddNote = async (title: string, content: string, folder: any, tags: string[]) => {
    const res = await fetch('/api/vault', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content, folder, tags })
    });
    const data = await res.json();
    fetchAllData();
    return data;
  };

  const handleAddSkill = async (name: string, description: string, code: string) => {
    const res = await fetch('/api/skills', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, code })
    });
    const data = await res.json();
    fetchAllData();
    return data;
  };

  const handleTriggerLoop = async (loopKey: string) => {
    const res = await fetch(`/api/loops/trigger/${loopKey}`, {
      method: 'POST'
    });
    const data = await res.json();
    fetchAllData();
    return data;
  };

  const handlePromoteCard = (id: string, nextStage: TrustStage) => {
    setStrategyCards(prev => prev.map(c => c.id === id ? { ...c, stage: nextStage } : c));
  };

  const handleUpdateRules = (id: string, ruleList: string[]) => {
    setStrategyCards(prev => prev.map(c => c.id === id ? { ...c, rules: ruleList } : c));
  };

  // Direct manual log injector
  const handleAddLogMessage = async (text: string, level: any, source: string) => {
    await fetch('/api/logs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source, level, text })
    });
    fetchAllData();
  };

  return (
    <div id="dashboard-canvas" className="min-h-screen bg-[#05070a] text-slate-300 font-sans selection:bg-cyan-500/30 select-none pb-12 antialiased border-4 border-slate-900 bg-[radial-gradient(circle_at_50%_0%,_rgba(15,23,42,0.65)_0%,_rgba(5,7,10,1)_100%)]">
      
      {/* Premium Immersive Header Layout */}
      <header id="dashboard-navbar" className="h-18 flex items-center justify-between px-6 border-b border-white/5 bg-slate-900/20 backdrop-blur-md sticky top-0 z-50">
        <div id="navbar-inner" className="w-full max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div id="branding-header" className="flex items-center space-x-4">
            {/* Custom vector launcher icon */}
            <div className="w-8 h-8 rounded-sm bg-slate-900/40 border-2 border-cyan-500 flex items-center justify-center shrink-0 shadow-[0_0_8px_rgba(6,182,212,0.45)]">
              <span className="font-mono text-cyan-500 font-bold text-xs tracking-tighter">H</span>
            </div>
            <div>
              <h1 id="app-heading" className="text-base font-bold tracking-widest font-mono text-white leading-tight">
                HERMES <span className="text-cyan-500">TRADING AGENT</span>
              </h1>
              <p className="text-[9px] text-slate-500 font-mono uppercase tracking-tighter">
                v4.1.0-PROD // SMC/ICT ARCHITECTURE
              </p>
            </div>
          </div>

          <div id="header-right-side" className="flex flex-wrap items-center gap-6">
            {/* Quick Metrics display */}
            <div id="ticker-metrics-strip" className="flex items-center gap-4 text-[10px] font-mono select-text bg-slate-900/30 border border-white/5 py-1.5 px-3 rounded">
              <div>
                <span className="text-slate-500 font-bold uppercase text-[9px] mr-1">Asset:</span>
                <strong className="text-slate-300 font-bold">XAUUSD</strong>
              </div>
              <div className="w-[1px] h-3 bg-white/5"></div>
              <div>
                <span className="text-slate-500 font-bold uppercase text-[9px] mr-1">Price:</span>
                <strong className="text-cyan-400 font-extrabold shadow-cyan-500/20">${marketMetrics.currentPrice.toFixed(2)}</strong>
              </div>
              <div className="w-[1px] h-3 bg-white/5"></div>
              <div>
                <span className="text-slate-500 font-bold uppercase text-[9px] mr-1">Ollama:</span>
                <strong className={status.ollama === 'connected' ? 'text-cyan-400' : 'text-amber-500'}>
                  {status.ollama === 'connected' ? 'ONLINE' : 'OFFLINE'}
                </strong>
              </div>
            </div>

            <div className="hidden md:flex items-center space-x-6">
              <div className="flex flex-col items-end">
                <span className="text-[9px] text-slate-500 uppercase font-mono font-medium">Staged Trust Level</span>
                <span className="text-[11px] font-bold text-amber-500 font-mono bg-amber-500/5 border border-amber-500/20 px-2 py-0.5 rounded-sm">PAPER_TRADING_ACTIVE</span>
              </div>
              <div className="h-8 w-[1px] bg-white/10"></div>
              <div className="flex flex-col items-end">
                <span className="text-[9px] text-slate-500 uppercase font-mono font-medium">Connectivity</span>
                <div className="flex space-x-1 mt-1">
                  <div className="w-2 h-2 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.8)]"></div>
                  <div className="w-2 h-2 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.8)]"></div>
                  <div className="w-2 h-2 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.8)]"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Grid Wrapper */}
      <main id="main-content-flow" className="max-w-7xl mx-auto px-6 mt-6 space-y-6">
        
        {/* Host Socket Middleware status */}
        <StatusCard status={status} onRefresh={handleRefreshStatus} loading={loading} />

        {/* Dashboard Sections Tab Controls */}
        <div id="tabs-deck" className="border-b border-white/5 pb-2 flex flex-wrap gap-2">
          <button
            id="tab-btn-terminal"
            onClick={() => setActiveTab('terminal')}
            className={`flex items-center space-x-2 py-2 px-4 rounded font-mono text-[11px] font-semibold tracking-wider cursor-pointer transition-all ${
              activeTab === 'terminal' 
                ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)] font-bold' 
                : 'bg-slate-900/20 text-slate-450 border border-white/5 hover:text-slate-200 hover:bg-slate-900/40'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>AGENT TERMINAL</span>
          </button>

          <button
            id="tab-btn-trades"
            onClick={() => setActiveTab('trades')}
            className={`flex items-center space-x-2 py-2 px-4 rounded font-mono text-[11px] font-semibold tracking-wider cursor-pointer transition-all ${
              activeTab === 'trades' 
                ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)] font-bold' 
                : 'bg-slate-900/20 text-slate-450 border border-white/5 hover:text-slate-200 hover:bg-slate-900/40'
            }`}
          >
            <LineChart className="w-3.5 h-3.5" />
            <span>TRADE DESK</span>
          </button>

          <button
            id="tab-btn-strategies"
            onClick={() => setActiveTab('strategies')}
            className={`flex items-center space-x-2 py-2 px-4 rounded font-mono text-[11px] font-semibold tracking-wider cursor-pointer transition-all ${
              activeTab === 'strategies' 
                ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)] font-bold' 
                : 'bg-slate-900/20 text-slate-450 border border-white/5 hover:text-slate-200 hover:bg-slate-900/40'
            }`}
          >
            <Settings2 className="w-3.5 h-3.5" />
            <span>STRATEGY STUDIO</span>
          </button>

          <button
            id="tab-btn-vault"
            onClick={() => setActiveTab('vault')}
            className={`flex items-center space-x-2 py-2 px-4 rounded font-mono text-[11px] font-semibold tracking-wider cursor-pointer transition-all ${
              activeTab === 'vault' 
                ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)] font-bold' 
                : 'bg-slate-900/20 text-slate-450 border border-white/5 hover:text-slate-200 hover:bg-slate-900/40'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>OBSIDIAN VAULT</span>
          </button>

          <button
            id="tab-btn-loops"
            onClick={() => setActiveTab('loops')}
            className={`flex items-center space-x-2 py-2 px-4 rounded font-mono text-[11px] font-semibold tracking-wider cursor-pointer transition-all ${
              activeTab === 'loops' 
                ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)] font-bold' 
                : 'bg-slate-900/20 text-slate-450 border border-white/5 hover:text-slate-200 hover:bg-slate-900/40'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>AUTONOMOUS LOOPS</span>
          </button>
        </div>

        {/* Dynamic Display Board mapping */}
        <div id="display-workspace">
          {activeTab === 'terminal' && (
            <AgentTerminal logs={logs} onAddLog={handleAddLogMessage} />
          )}

          {activeTab === 'trades' && (
            <TradeMonitor
              metrics={marketMetrics}
              activeTrades={activeTrades}
              closedTrades={closedTrades}
              balance={balance}
              equity={equity}
              dailyDD={dailyDD}
              weeklyDD={weeklyDD}
              onPlaceTrade={handlePlaceTrade}
              onCloseTrade={handleCloseTrade}
            />
          )}

          {activeTab === 'strategies' && (
            <StrategyStudio
              cards={strategyCards}
              onPromoteCard={handlePromoteCard}
              onUpdateRules={handleUpdateRules}
            />
          )}

          {activeTab === 'vault' && (
            <KnowledgeExplorer notes={notes} onAddNote={handleAddNote} />
          )}

          {activeTab === 'loops' && (
            <AutonomousLoops
              skills={skills}
              loops={loops}
              onTriggerLoop={handleTriggerLoop}
              onAddSkill={handleAddSkill}
            />
          )}
        </div>

      </main>
    </div>
  );
}
