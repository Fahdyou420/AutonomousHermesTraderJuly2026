import React, { useState, useEffect } from 'react';
import { Trade, MarketMetrics, TrustStage } from '../types';
import { LineChart, Line, XAxis, YAxis, ReferenceLine, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Shield, Sparkles, TrendingUp, AlertTriangle, ArrowUpRight, ArrowDownRight, ClipboardList, Trash2, Crosshair } from 'lucide-react';

interface TradeMonitorProps {
  metrics: MarketMetrics;
  activeTrades: Trade[];
  closedTrades: Trade[];
  balance: number;
  equity: number;
  dailyDD: number;
  weeklyDD: number;
  onPlaceTrade: (tradeParams: any) => Promise<any>;
  onCloseTrade: (id: string) => Promise<any>;
}

export default function TradeMonitor({
  metrics,
  activeTrades,
  closedTrades,
  balance,
  equity,
  dailyDD,
  weeklyDD,
  onPlaceTrade,
  onCloseTrade
}: TradeMonitorProps) {
  // Line chart price ticks tracking
  const [chartData, setChartData] = useState<any[]>([]);
  
  // Order desk form states
  const [direction, setDirection] = useState<'BUY' | 'SELL'>('BUY');
  const [setupType, setSetupType] = useState('Order Block Tap');
  const [stopLossOffset, setStopLossOffset] = useState('5.0'); // $5 gold move
  const [riskPercent, setRiskPercent] = useState('0.8'); // Under max 1.0% limit
  const [stage, setStage] = useState<TrustStage>('paper');
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Auto compile chart tick data
  useEffect(() => {
    setChartData(prev => {
      const nowStr = new Date().toLocaleTimeString();
      const updated = [...prev, { time: nowStr, price: metrics.currentPrice }];
      if (updated.length > 25) updated.shift();
      return updated;
    });
  }, [metrics.currentPrice]);

  const calculateLotSize = (balanceNum: number, stopLossVal: number, riskPct: number) => {
    if (stopLossVal <= 0 || balanceNum <= 0 || riskPct <= 0) return 1.0;
    // Gold contract multiplier (usually 1 Lot = 100oz).
    // Risk = Lot * StopLossPriceDistance * 100
    // Lot = RiskAmount / (StopLossPriceDistance * 100)
    const riskAmount = balanceNum * (riskPct / 100);
    const lot = riskAmount / (stopLossVal * 100);
    return Math.max(0.01, parseFloat(lot.toFixed(2)));
  };

  const calculatedStopLoss = direction === 'BUY'
    ? parseFloat((metrics.currentPrice - parseFloat(stopLossOffset)).toFixed(2))
    : parseFloat((metrics.currentPrice + parseFloat(stopLossOffset)).toFixed(2));

  const calculatedTakeProfit = direction === 'BUY'
    ? parseFloat((metrics.currentPrice + parseFloat(stopLossOffset) * 2.5).toFixed(2)) // 1:2.5 RR ratio
    : parseFloat((metrics.currentPrice - parseFloat(stopLossOffset) * 2.5).toFixed(2));

  const calculatedLots = calculateLotSize(balance, parseFloat(stopLossOffset), parseFloat(riskPercent));

  const handleOrderSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    const riskNum = parseFloat(riskPercent);
    if (isNaN(riskNum) || riskNum > 1.0) {
      setErrorMsg("SMC Gatekeeper violation: Risk cannot exceed maximum allowed 1.0% per setup.");
      return;
    }

    try {
      const p = {
        direction,
        type: setupType,
        entryPrice: metrics.currentPrice,
        stopLoss: calculatedStopLoss,
        takeProfit: calculatedTakeProfit,
        lotSize: calculatedLots,
        stage,
        riskPercent: riskNum
      };

      const result = await onPlaceTrade(p);
      if (result) {
        setSuccessMsg(`ZeroMQ order successfully dispatched: MT5 EA linked for ${calculatedLots} lots.`);
        setTimeout(() => setSuccessMsg(''), 4000);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error occurred while calling ZeroMQ ordering socket.');
    }
  };

  return (
    <div id="trade-monitor-panel" className="space-y-6">
      
      {/* Visual Analytics Widgets */}
      <div id="equity-grid-widgets" className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Balance */}
        <div className="bg-slate-950/45 border border-white/5 p-4 rounded-sm backdrop-blur-md flex flex-col justify-between shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <span className="text-slate-500 text-[10px] uppercase font-mono font-bold tracking-widest">Nominal Balance</span>
          <p className="text-xl font-bold font-mono text-white">${balance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
          <span className="text-[9px] text-emerald-400 font-mono mt-1 font-semibold">MT5 Terminal Synced</span>
        </div>

        {/* Live Equity */}
        <div className="bg-slate-950/45 border border-white/5 p-4 rounded-sm backdrop-blur-md flex flex-col justify-between shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <span className="text-slate-450 text-[10px] uppercase font-mono font-bold tracking-widest">Active Equity</span>
          <p className="text-xl font-bold font-mono text-cyan-400">${equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
          <span className={`text-[9px] font-mono mt-1 font-semibold ${equity >= balance ? 'text-emerald-400' : 'text-rose-455'}`}>
            {equity >= balance ? `+$${(equity - balance).toFixed(2)} active floating` : `-$${(balance - equity).toFixed(2)} floating DD`}
          </span>
        </div>

        {/* Daily Drawdown telemetry (Check risk max 4%) */}
        <div className="bg-slate-950/45 border border-white/5 p-4 rounded-sm backdrop-blur-md flex flex-col justify-between shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div className="flex items-center justify-between">
            <span className="text-slate-450 text-[10px] uppercase font-mono font-bold tracking-widest">Daily DD Limit</span>
            <Shield className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          </div>
          <p className="text-xl font-bold font-mono text-cyan-400">{dailyDD.toFixed(2)}% <span className="text-[10px] text-slate-500 font-normal">/ 4.0%</span></p>
          <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden mt-1 border border-white/5 shadow-inner">
            <div className="bg-cyan-500/80 h-full transition-all" style={{ width: `${Math.min(100, (dailyDD / 4.0) * 100)}%` }}></div>
          </div>
        </div>

        {/* Weekly Drawdown telemetry (Check risk max 8%) */}
        <div className="bg-slate-950/45 border border-white/5 p-4 rounded-sm backdrop-blur-md flex flex-col justify-between shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div className="flex items-center justify-between">
            <span className="text-slate-450 text-[10px] uppercase font-mono font-bold tracking-widest">Weekly DD Limit</span>
            <Shield className="w-3.5 h-3.5 text-cyan-455" />
          </div>
          <p className="text-xl font-bold font-mono text-cyan-455">{weeklyDD.toFixed(2)}% <span className="text-[10px] text-slate-500 font-normal">/ 8.0%</span></p>
          <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden mt-1 border border-white/5 shadow-inner">
            <div className="bg-cyan-600/80 h-full transition-all" style={{ width: `${Math.min(100, (weeklyDD / 8.0) * 100)}%` }}></div>
          </div>
        </div>
      </div>

      {/* Main Splits: Interactive Chart & Trade Order Desk */}
      <div id="chart-and-desk-split" className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* SMC Live Price Action Chart with overplayed FVGs/OBs */}
        <div id="recharts-gold-container" className="lg:col-span-2 bg-slate-950/45 border border-white/5 rounded-sm p-5 flex flex-col shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/5">
            <div className="flex items-center space-x-2">
              <Crosshair className="w-4 h-4 text-cyan-400 animate-pulse animate-spin-slow" />
              <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-widest">XAUUSD Spot Gold Live Feed</span>
            </div>
            <div className="flex items-center space-x-4 text-[10px] font-mono text-slate-500">
              <span className="flex items-center space-x-1">
                <span className="w-2.5 h-1.5 bg-emerald-505/20 border border-emerald-500/25"></span>
                <span>Active Bullish FVG</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2.5 h-1.5 bg-cyan-705/20 border border-cyan-500/25"></span>
                <span>Bearish OB</span>
              </span>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                <XAxis dataKey="time" stroke="#475569" fontSize={8} fontFamily="JetBrains Mono" />
                <YAxis domain={['auto', 'auto']} stroke="#475569" fontSize={8} fontFamily="JetBrains Mono" />
                <Tooltip contentStyle={{ backgroundColor: '#070a0f', borderColor: 'rgba(255,255,255,0.08)', fontSize: '10px', fontFamily: 'JetBrains Mono', color: '#cyan' }} />
                
                {/* Horizontal Indicators Reference Lines for SMC zones */}
                {metrics.fairValueGaps.filter(f => f.status === 'ACTIVE').map(f => (
                  <ReferenceLine
                    key={f.id}
                    y={f.midPoint}
                    stroke="#10b981"
                    strokeDasharray="4 4"
                    label={{ value: `Bullish FVG [${f.low}-${f.high}]`, fill: '#10b981', fontSize: 8, fontFamily: 'JetBrains Mono', position: 'insideTopLeft' }}
                  />
                ))}

                {metrics.orderBlocks.filter(o => o.status === 'ACTIVE').map(o => (
                  <ReferenceLine
                    key={o.id}
                    y={(o.top + o.bottom) / 2}
                    stroke={o.direction === 'BULLISH' ? '#10b981' : '#a855f7'}
                    strokeDasharray="4 4"
                    label={{ value: `Bearish OB [${o.bottom}-${o.top}]`, fill: o.direction === 'BULLISH' ? '#10b981' : '#06b6d4', fontSize: 8, fontFamily: 'JetBrains Mono', position: 'insideBottomRight' }}
                  />
                ))}

                {/* Real-time Session High and Low Reference Markers */}
                {metrics.dailyHigh && (
                  <ReferenceLine
                    y={metrics.dailyHigh}
                    stroke="#ef4444"
                    strokeDasharray="3 3"
                    strokeWidth={1}
                    label={{ value: `Session High: $${metrics.dailyHigh.toFixed(2)}`, fill: '#f87171', fontSize: 8, fontFamily: 'JetBrains Mono', position: 'insideTopRight' }}
                  />
                )}
                {metrics.dailyLow && (
                  <ReferenceLine
                    y={metrics.dailyLow}
                    stroke="#3b82f6"
                    strokeDasharray="3 3"
                    strokeWidth={1}
                    label={{ value: `Session Low: $${metrics.dailyLow.toFixed(2)}`, fill: '#60a5fa', fontSize: 8, fontFamily: 'JetBrains Mono', position: 'insideBottomRight' }}
                  />
                )}

                <Line
                  type="monotone"
                  dataKey="price"
                  stroke="#06b6d4"
                  strokeWidth={2}
                  dot={false}
                  animationDuration={300}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-3 gap-3 mt-4 pt-3 border-t border-white/5 text-[10px] font-mono">
            <div>
              <span className="text-slate-500 block uppercase font-bold text-[8px]">Current Ask</span>
              <span className="text-cyan-400 font-bold text-sm tracking-widest">${metrics.currentPrice.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-slate-500 block uppercase font-bold text-[8px]">Daily High</span>
              <span className="text-slate-350 font-bold">${metrics.dailyHigh.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-slate-500 block uppercase font-bold text-[8px]">Daily Low</span>
              <span className="text-slate-400 font-bold">${metrics.dailyLow.toFixed(2)}</span>
            </div>
          </div>
        </div>

        {/* Order Desk Ticket Form */}
        <div id="order-desk-container" className="bg-slate-950/45 border border-white/5 rounded-sm p-5 flex flex-col justify-between shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div>
            <div className="flex items-center space-x-1.5 mb-4 pb-2 border-b border-white/5">
              <Crosshair className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-widest">SMC Order Router Ticket</span>
            </div>

            <form onSubmit={handleOrderSubmit} className="space-y-4">
              {/* Buy Sell Switch */}
              <div className="grid grid-cols-2 gap-2 bg-slate-950/60 p-1 rounded-sm border border-white/5 text-xs font-mono">
                <button
                  type="button"
                  onClick={() => setDirection('BUY')}
                  className={`py-1.5 rounded-sm transition-all cursor-pointer font-bold text-[11px] ${direction === 'BUY' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 shadow-[0_0_8px_rgba(16,185,129,0.06)]' : 'text-slate-500 hover:text-slate-300'}`}
                >
                  BUY SPOT
                </button>
                <button
                  type="button"
                  onClick={() => setDirection('SELL')}
                  className={`py-1.5 rounded-sm transition-all cursor-pointer font-bold text-[11px] ${direction === 'SELL' ? 'bg-rose-500/10 text-rose-450 border border-rose-500/25 shadow-[0_0_8px_rgba(239,68,68,0.06)]' : 'text-slate-500 hover:text-slate-300'}`}
                >
                  SELL SHORT
                </button>
              </div>

              {/* SMC Setup classification dropdown */}
              <div>
                <label className="block text-[8px] text-slate-500 font-mono uppercase font-bold mb-1">ICT/SMC Custom Setup Type</label>
                <select
                  className="w-full bg-slate-950 border border-white/5 p-2 rounded-sm text-xs text-slate-200 font-mono outline-none focus:border-cyan-500/40 transition-colors"
                  value={setupType}
                  onChange={(e) => setSetupType(e.target.value)}
                >
                  <option value="Order Block Tap">Bullish/Bearish Order Block Tap</option>
                  <option value="FVG Retest">Fair Value Gap (FVG) Retest</option>
                  <option value="Liquidity Sweep">External Liquidity Sweep</option>
                  <option value="Break of Structure">Displacement Break of Structure</option>
                </select>
              </div>

              {/* Stop loss size inputs */}
              <div className="grid grid-cols-2 gap-3 pb-1 border-b border-white/5">
                <div>
                  <label className="block text-[8px] text-slate-550 font-mono uppercase font-bold mb-1">Stop Loss Range ($)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="1.0"
                    required
                    className="w-full bg-slate-950 border border-white/5 p-2 rounded-sm text-xs text-slate-200 font-mono outline-none focus:border-cyan-500/40"
                    value={stopLossOffset}
                    onChange={(e) => setStopLossOffset(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-[8px] text-slate-550 font-mono uppercase font-bold mb-1">Exposure risk (%)</label>
                  <input
                    type="number"
                    step="0.05"
                    min="0.1"
                    max="5.0"
                    required
                    className={`w-full bg-slate-950 border p-2 rounded-sm text-xs font-mono outline-none transition-all ${parseFloat(riskPercent) > 1.0 ? 'border-red-500 text-red-400 focus:border-red-500' : 'border-white/5 text-slate-200 focus:border-cyan-500/40'}`}
                    value={riskPercent}
                    onChange={(e) => setRiskPercent(e.target.value)}
                  />
                  {parseFloat(riskPercent) > 1.0 && (
                    <span className="text-[7px] text-red-400 font-bold block mt-0.5">EXCEEDS 1.0% MAX MANDATE</span>
                  )}
                </div>
              </div>

              {/* Dynamic calculated values box */}
              <div className="p-3 bg-slate-950/40 border border-white/5 rounded-sm text-[10px] font-mono text-slate-450 space-y-1.5 shadow-inner">
                <div className="flex justify-between">
                  <span>Entry price reference:</span>
                  <span className="text-slate-200 font-semibold">${metrics.currentPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-rose-455">
                  <span>Calculated SL Limit:</span>
                  <span className="font-semibold">${calculatedStopLoss.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-cyan-400">
                  <span>Calculated TP Target:</span>
                  <span className="font-semibold">${calculatedTakeProfit.toFixed(2)}</span>
                </div>
                <div className="flex justify-between border-t border-white/5 pt-1.5 font-bold">
                  <span>Computed Lot Contract:</span>
                  <span className="text-cyan-400">{calculatedLots} Lots</span>
                </div>
              </div>

              {/* Action Stage pipeline selector */}
              <div>
                <label className="block text-[8px] text-slate-550 font-mono uppercase font-bold mb-1">Submit Order Target Pipeline</label>
                <div className="grid grid-cols-3 gap-1 text-[8px] font-mono text-center">
                  {(['paper', 'live_candidate', 'live'] as TrustStage[]).map(st => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => setStage(st)}
                      className={`p-1.5 border rounded-sm capitalize cursor-pointer transition-all ${stage === st ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 font-bold' : 'bg-slate-950 text-slate-500 border-white/5'}`}
                    >
                      {st.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>

              {/* Status responses inside desk */}
              {errorMsg && (
                <div className="p-2 border border-red-500/20 bg-red-550/5 text-red-400 text-[9px] font-mono rounded-sm flex items-start space-x-1">
                  <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {successMsg && (
                <div className="p-2 border border-cyan-500/20 bg-cyan-555/5 text-cyan-400 text-[9px] font-mono rounded-sm flex items-start space-x-1 animate-pulse">
                  <Sparkles className="w-3 h-3 shrink-0 mt-0.5" />
                  <span>{successMsg}</span>
                </div>
              )}

              {/* Dispatch Socket Trigger */}
              <button
                id="btn-execute-order"
                type="submit"
                className={`w-full font-mono font-bold text-xs py-2.5 rounded-sm transition-all flex items-center justify-center space-x-1 cursor-pointer ${
                  parseFloat(riskPercent) > 1.0 ? 'bg-slate-900 border border-slate-800 text-slate-600 pointer-events-none' : 'bg-slate-900/40 border border-white/5 hover:border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/15 active:bg-slate-950 h-10 shadow-[0_4px_12px_rgba(6,182,212,0.05)]'
                }`}
              >
                <ArrowUpRight className="w-4 h-4" />
                <span>ROUTE ORDER TICKETS (PORT 5557)</span>
              </button>
            </form>
          </div>

          <p className="text-[8px] text-slate-550 text-center font-mono mt-2 uppercase tracking-wide">
            Staged trust authorization active. Real orders require live pipeline clearance.
          </p>
        </div>
      </div>

      {/* Split Grid: Bottom layout showing Active positions & Historic reviews */}
      <div id="position-checklists" className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        
        {/* Active Open Positions */}
        <div id="active-positions" className="bg-slate-950/45 border border-white/5 rounded-sm p-5 shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/5">
            <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-widest">Live MT5 & Paper Positions</span>
            <span className="text-[10px] font-mono text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-0.5 rounded font-bold uppercase shrink-0">
              {activeTrades.length} ACTIVE CONTRACTS
            </span>
          </div>

          <div className="space-y-3.5 max-h-[300px] overflow-y-auto">
            {activeTrades.map(trade => (
              <div id={`active-trade-${trade.id}`} key={trade.id} className="p-4 border border-white/5 bg-slate-950/40 rounded-sm flex flex-col justify-between space-y-4 hover:border-cyan-500/15 transition-all">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-sm ${trade.direction === 'BUY' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-455 border border-rose-500/20'}`}>
                      {trade.direction}
                    </span>
                    <span className="text-xs font-bold font-mono text-slate-200">XAUUSD Spot Gold</span>
                    <span className="text-[9px] text-slate-450 font-mono px-1.5 py-0.2 bg-slate-900/40 border border-white/5 rounded-sm capitalize">
                      {trade.stage}
                    </span>
                  </div>

                  <p className={`text-sm font-bold font-mono ${trade.pnl >= 0 ? 'text-emerald-400' : 'text-rose-455'}`}>
                    {trade.pnl >= 0 ? `+$${trade.pnl.toFixed(2)}` : `-$${Math.abs(trade.pnl).toFixed(2)}`}
                  </p>
                </div>

                <div className="grid grid-cols-4 gap-2 text-[10px] font-mono text-slate-400 border-t border-b border-white/5 py-2">
                  <div>
                    <span className="text-[8px] text-slate-500 uppercase font-semibold">Entry Ticket</span>
                    <p className="text-slate-200 font-semibold">${trade.entryPrice.toFixed(2)}</p>
                  </div>
                  <div>
                    <span className="text-[8px] text-slate-500 uppercase font-semibold">Current bid</span>
                    <p className="text-slate-300 font-semibold">${trade.currentPrice.toFixed(2)}</p>
                  </div>
                  <div>
                    <span className="text-[8px] text-slate-500 uppercase font-semibold">Stop Loss</span>
                    <p className="text-rose-455 font-semibold">${trade.stopLoss.toFixed(2)}</p>
                  </div>
                  <div>
                    <span className="text-[8px] text-slate-500 uppercase font-semibold">Take Profit</span>
                    <p className="text-emerald-400 font-semibold">${trade.takeProfit.toFixed(2)}</p>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <p className="text-[9px] text-slate-450 font-mono max-w-sm truncate whitespace-pre-wrap">
                    Setup: <strong className="text-cyan-400">{trade.type}</strong> | {trade.notes}
                  </p>
                  <button
                    id={`btn-close-position-${trade.id}`}
                    onClick={() => onCloseTrade(trade.id)}
                    className="p-1 px-3 text-[9px] bg-slate-905/40 hover:bg-rose-500/10 active:bg-rose-500/20 text-rose-455 border border-white/5 hover:border-rose-500/30 rounded-sm font-mono transition-all cursor-pointer flex items-center space-x-1 shrink-0 shadow-[0_0_6px_rgba(239,68,68,0.05)]"
                  >
                    <Trash2 className="w-3 h-3" />
                    <span>LIQUID POSITION</span>
                  </button>
                </div>
              </div>
            ))}

            {activeTrades.length === 0 && (
              <div className="flex flex-col items-center justify-center p-8 border border-white/5 rounded-sm border-dashed text-slate-500 text-xs font-mono bg-slate-900/5">
                <ClipboardList className="w-8 h-8 text-slate-700 mb-1" />
                <p>No open positions. Use order router ticket desk above.</p>
              </div>
            )}
          </div>
        </div>

        {/* Historic Trades ledger & stats */}
        <div id="closed-trades" className="bg-slate-950/45 border border-white/5 rounded-sm p-5 shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/5">
            <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-widest">Historic Closed Reviews</span>
            <span className="text-[10px] font-mono text-slate-500 select-none">
              Verified Staged Transactions log
            </span>
          </div>

          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {closedTrades.slice().reverse().map(trade => (
              <div id={`closed-trade-${trade.id}`} key={trade.id} className="p-3 border border-white/5 bg-slate-950/20 rounded-sm text-[10px] font-mono flex items-center justify-between hover:border-cyan-500/15 transition-all">
                <div className="space-y-1 overflow-hidden pr-2">
                  <div className="flex items-center space-x-1.5">
                    <span className={`text-[8px] font-bold px-1.5 rounded-sm ${trade.direction === 'BUY' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/15' : 'bg-rose-500/10 text-rose-455 border border-rose-500/15'}`}>
                      {trade.direction}
                    </span>
                    <strong className="text-slate-300 font-semibold">PF: {trade.rrRatio}R</strong>
                    <span className="text-[8px] text-slate-500 capitalize">{trade.stage}</span>
                  </div>
                  <p className="text-slate-450 text-[8px] truncate">{trade.type}: {trade.notes}</p>
                </div>

                <div className="text-right shrink-0">
                  <p className={`font-bold text-xs ${trade.pnl >= 0 ? 'text-emerald-400' : 'text-rose-455'}`}>
                    {trade.pnl >= 0 ? `+$${trade.pnl.toFixed(2)}` : `-$${Math.abs(trade.pnl).toFixed(2)}`}
                  </p>
                  <span className="text-[8px] text-slate-600 block mt-0.5">{trade.closedAt ? new Date(trade.closedAt).toLocaleDateString() : 'closed'}</span>
                </div>
              </div>
            ))}

            {closedTrades.length === 0 && (
              <p className="text-center text-xs text-slate-500 py-8 font-mono">No historical records in session memory.</p>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
