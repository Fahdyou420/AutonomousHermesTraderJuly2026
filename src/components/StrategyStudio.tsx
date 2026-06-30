import React, { useState } from 'react';
import { StrategyCard, TrustStage } from '../types';
import { Shield, Sparkles, TrendingUp, AlertOctagon, CheckSquare, Settings2, Sliders, ChevronRight } from 'lucide-react';

interface StrategyStudioProps {
  cards: StrategyCard[];
  onPromoteCard: (id: string, nextStage: TrustStage) => void;
  onUpdateRules: (id: string, rules: string[]) => void;
}

export default function StrategyStudio({ cards, onPromoteCard, onUpdateRules }: StrategyStudioProps) {
  const [selectedCard, setSelectedCard] = useState<StrategyCard | null>(cards[0] || null);
  const [editingRules, setEditingRules] = useState<string>('');
  const [showRuleEditor, setShowRuleEditor] = useState(false);

  const getStageHeaderColor = (stage: TrustStage) => {
    switch (stage) {
      case 'hypothesis': return 'border-slate-700 bg-slate-900 text-slate-400';
      case 'backtest': return 'border-sky-800 bg-sky-950/20 text-sky-400';
      case 'paper': return 'border-purple-800 bg-purple-950/20 text-purple-400';
      case 'live_candidate': return 'border-amber-800 bg-amber-950/20 text-amber-400';
      case 'live': return 'border-emerald-800 bg-emerald-950/25 text-emerald-400';
    }
  };

  const promoteStage = (stage: TrustStage): TrustStage | null => {
    switch (stage) {
      case 'hypothesis': return 'backtest';
      case 'backtest': return 'paper';
      case 'paper': return 'live_candidate';
      case 'live_candidate': return 'live';
      default: return null;
    }
  };

  const demoteStage = (stage: TrustStage): TrustStage | null => {
    switch (stage) {
      case 'live': return 'live_candidate';
      case 'live_candidate': return 'paper';
      case 'paper': return 'backtest';
      case 'backtest': return 'hypothesis';
      default: return null;
    }
  };

  const handlePromote = (card: StrategyCard) => {
    const next = promoteStage(card.stage);
    if (next) {
      onPromoteCard(card.id, next);
      setSelectedCard(prev => prev && prev.id === card.id ? { ...prev, stage: next } : prev);
    }
  };

  const handleDemote = (card: StrategyCard) => {
    const prev = demoteStage(card.stage);
    if (prev) {
      onPromoteCard(card.id, prev);
      setSelectedCard(p => p && p.id === card.id ? { ...p, stage: prev } : p);
    }
  };

  const startEditRules = (card: StrategyCard) => {
    setEditingRules(card.rules.join('\n'));
    setShowRuleEditor(true);
  };

  const saveRules = (card: StrategyCard) => {
    const ruleList = editingRules.split('\n').map(r => r.trim()).filter(Boolean);
    onUpdateRules(card.id, ruleList);
    setSelectedCard(prev => prev && prev.id === card.id ? { ...prev, rules: ruleList } : prev);
    setShowRuleEditor(false);
  };

  return (
    <div id="strategy-studio-panel" className="bg-slate-950/45 border border-white/5 rounded backdrop-blur-md p-5 shadow-[0_4px_24px_rgba(0,0,0,0.4)]">
      <div id="studio-header" className="flex items-center justify-between mb-5">
        <div id="studio-title-block" className="flex items-center space-x-2">
          <Settings2 className="w-4 h-4 text-cyan-400 animate-spin-slow" />
          <h2 className="text-xs font-bold tracking-widest text-slate-400 uppercase font-mono">
            SMC Strategy Studio & Staged Trust (Layer 3b)
          </h2>
        </div>
        <div className="flex items-center space-x-2 text-[9px] text-slate-500 font-mono font-medium uppercase">
          <Shield className="w-3.5 h-3.5 text-cyan-400" />
          <span>Compliance check: max 1% risk per trade</span>
        </div>
      </div>

      <div id="studio-grid" className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Side: Strategy Card Pipeline */}
        <div id="studio-pipeline" className="lg:col-span-1 space-y-3.5">
          <p className="text-[9px] font-mono text-slate-505 uppercase font-bold tracking-wider mb-2">Strategy Model Library</p>
          {cards.map(card => (
            <button
              id={`strategy-card-${card.id}`}
              key={card.id}
              onClick={() => { setSelectedCard(card); setShowRuleEditor(false); }}
              className={`w-full text-left p-4 rounded-sm border transition-all cursor-pointer flex flex-col justify-between h-[120px] ${
                selectedCard?.id === card.id
                  ? 'bg-slate-950/60 border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.08)]'
                  : 'bg-slate-900/10 border-white/5 hover:border-slate-800'
              }`}
            >
              <div className="flex items-start justify-between w-full">
                <div className="overflow-hidden pr-2">
                  <h3 className="text-xs font-mono font-bold text-slate-200 truncate">{card.title}</h3>
                  <span className="text-[9px] text-slate-500 font-mono">XAUUSD Spot Gold</span>
                </div>
                <span className={`text-[8px] font-bold tracking-widest font-mono uppercase px-2 py-0.5 rounded border ${
                  card.stage === 'live' ? 'border-emerald-500/20 text-emerald-400 bg-emerald-500/5' :
                  card.stage === 'live_candidate' ? 'border-amber-500/20 text-amber-400 bg-amber-500/5' :
                  card.stage === 'paper' ? 'border-cyan-500/20 text-cyan-400 bg-cyan-500/5' :
                  card.stage === 'backtest' ? 'border-sky-500/20 text-sky-450 bg-sky-500/5' : 'border-slate-800 text-slate-505 bg-slate-900'
                }`}>
                  {card.stage}
                </span>
              </div>
              
              <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-white/5">
                <div className="flex flex-col text-[10px] font-mono">
                  <span className="text-slate-500 text-[8px] uppercase">Win Rate</span>
                  <span className="text-slate-200 font-bold">{card.winRate}%</span>
                </div>
                <div className="flex flex-col text-[10px] font-mono">
                  <span className="text-slate-500 text-[8px] uppercase">Prof. Fac</span>
                  <span className="text-cyan-400 font-bold">{card.profitFactor}</span>
                </div>
                <div className="flex flex-col text-[10px] font-mono">
                  <span className="text-slate-500 text-[8px] uppercase">Trades</span>
                  <span className="text-slate-450 font-bold">{card.totalTrades}</span>
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Right Side: Strategy Detail, Staged Trust Stage Control Panel & Rules config */}
        <div id="studio-details" className="lg:col-span-2 bg-slate-950/20 border border-white/5 rounded-sm p-5 flex flex-col justify-between">
          {selectedCard ? (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-white/5">
                <div>
                  <h3 className="text-xs font-bold text-slate-100 font-mono uppercase tracking-wider">{selectedCard.title}</h3>
                  <p className="text-[10px] text-slate-500 font-mono">Stage: <strong className="text-cyan-400 capitalize">{selectedCard.stage}</strong></p>
                </div>
                
                {/* Stage Progression control */}
                <div className="flex items-center space-x-2 bg-slate-950/50 border border-white/5 p-1.5 rounded-sm">
                  <button
                    onClick={() => handleDemote(selectedCard)}
                    disabled={selectedCard.stage === 'hypothesis'}
                    className="p-1 px-2.5 text-[10px] font-mono bg-slate-900/40 hover:bg-slate-850 active:bg-slate-950 text-slate-300 rounded border border-white/5 disabled:opacity-30 disabled:pointer-events-none cursor-pointer transition-colors"
                  >
                    Demote
                  </button>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-650 shrink-0" />
                  <button
                    onClick={() => handlePromote(selectedCard)}
                    disabled={selectedCard.stage === 'live'}
                    className="p-1 px-3.5 text-[10px] font-mono bg-slate-905/40 hover:bg-cyan-500/10 hover:border-cyan-500/30 active:bg-slate-950 text-cyan-400 rounded-sm border border-white/5 disabled:opacity-30 disabled:pointer-events-none cursor-pointer transition-all shadow-[0_0_6px_rgba(6,182,212,0.05)]"
                  >
                    Promote Stage
                  </button>
                </div>
              </div>

              {/* Progress Flow Graphic */}
              <div className="py-2">
                <p className="text-[9px] font-mono text-slate-500 uppercase tracking-widest font-bold mb-2">Staged Trust Progression Matrix</p>
                <div className="grid grid-cols-5 gap-1.5 text-[9px] font-mono text-center">
                  {(['hypothesis', 'backtest', 'paper', 'live_candidate', 'live'] as TrustStage[]).map(s => {
                    const isActive = selectedCard.stage === s;
                    const isPassed = ['hypothesis', 'backtest', 'paper', 'live_candidate', 'live'].indexOf(selectedCard.stage) >= ['hypothesis', 'backtest', 'paper', 'live_candidate', 'live'].indexOf(s);
                    
                    return (
                      <div
                        id={`progress-${s}`}
                        key={s}
                        className={`p-1.5 rounded-sm border transition-all ${
                          isActive ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400 font-bold shadow-[0_0_10px_rgba(6,182,212,0.08)]' :
                          isPassed ? 'bg-slate-900/40 border-white/5 text-slate-400' : 'bg-slate-950 text-slate-700 border-transparent'
                        }`}
                      >
                        <p className="uppercase text-[8px] truncate">{s.replace('_', ' ')}</p>
                        <span className="text-[7px] text-slate-550 block mt-0.5">{isActive ? '● CURRENT' : isPassed ? '✓ DONE' : 'WAIT'}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Description */}
              <div className="bg-slate-900/15 p-3 rounded-sm border border-white/5 font-sans text-xs text-slate-350 leading-relaxed">
                {selectedCard.description}
              </div>

              {/* Rules block */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[9px] font-mono text-slate-450 uppercase tracking-wider font-semibold">Trading Criteria & Core Execution Rules</span>
                  <button
                    onClick={() => showRuleEditor ? saveRules(selectedCard) : startEditRules(selectedCard)}
                    className="text-[10px] font-mono text-cyan-455 hover:text-cyan-355 cursor-pointer"
                  >
                    {showRuleEditor ? '[SAVE RULES]' : '[EDIT RULES]'}
                  </button>
                </div>

                {showRuleEditor ? (
                  <textarea
                    className="w-full h-32 bg-slate-900 border border-slate-800 rounded p-3 text-xs text-slate-100 font-mono outline-none focus:border-cyan-500"
                    value={editingRules}
                    onChange={(e) => setEditingRules(e.target.value)}
                  />
                ) : (
                  <div className="space-y-1.5 p-3 rounded-sm bg-slate-950/40 border border-white/5 max-h-[160px] overflow-y-auto">
                    {selectedCard.rules.map((rule, idx) => (
                      <div key={idx} className="flex items-start space-x-2 text-xs font-mono text-slate-350 leading-relaxed">
                        <CheckSquare className="w-3.5 h-3.5 text-cyan-400 mt-0.5 shrink-0" />
                        <span>{rule}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Risk boundaries visual validation box */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                <div className="bg-slate-900/20 p-2.5 border border-white/5 rounded-sm flex items-center space-x-2 text-[10px] font-mono">
                  <TrendingUp className="w-4 h-4 text-emerald-400 shrink-0" />
                  <div>
                    <p className="text-slate-500 text-[8px] uppercase font-bold">Max Risk Ratio</p>
                    <p className="text-slate-300 font-bold">{(selectedCard.riskModel.maxRisk * 100).toFixed(1)}% Risk / Trade</p>
                  </div>
                </div>
                <div className="bg-slate-900/20 p-2.5 border border-white/5 rounded-sm flex items-center space-x-2 text-[10px] font-mono">
                  <AlertOctagon className="w-4 h-4 text-amber-500 shrink-0" />
                  <div>
                    <p className="text-slate-500 text-[8px] uppercase font-bold">Daily DD Limit</p>
                    <p className="text-slate-300 font-bold">{(selectedCard.riskModel.maxDailyDD * 100).toFixed(1)}% Limit</p>
                  </div>
                </div>
                <div className="bg-slate-900/20 p-2.5 border border-white/5 rounded-sm flex items-center space-x-2 text-[10px] font-mono">
                  <AlertOctagon className="w-4 h-4 text-red-500 shrink-0" />
                  <div>
                    <p className="text-slate-500 text-[8px] uppercase font-bold">Weekly DD Limit</p>
                    <p className="text-slate-300 font-bold">{(selectedCard.riskModel.maxWeeklyDD * 100).toFixed(1)}% Limit</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-505 font-mono text-xs">
              <Sparkles className="w-6 h-6 mr-2 text-cyan-400 animate-spin" />
              <span>Selecting strategy model...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
