import React, { useState } from 'react';
import { SkillCard } from '../types';
import { Shield, Sparkles, RefreshCw, Cpu, Code2, Play, Terminal, HelpCircle, CheckCircle } from 'lucide-react';

interface AutonomousLoopsProps {
  skills: SkillCard[];
  loops: any;
  onTriggerLoop: (loopKey: string) => Promise<any>;
  onAddSkill: (name: string, description: string, code: string) => void;
}

export default function AutonomousLoops({ skills, loops, onTriggerLoop, onAddSkill }: AutonomousLoopsProps) {
  const [selectedSkill, setSelectedSkill] = useState<SkillCard | null>(skills[0] || null);
  const [triggeringKey, setTriggeringKey] = useState<string | null>(null);

  // Auto add custom developer skills if desired
  const [customName, setCustomName] = useState('');
  const [customDesc, setCustomDesc] = useState('');
  const [customCode, setCustomCode] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  const handleTrigger = async (key: string) => {
    setTriggeringKey(key);
    try {
      await onTriggerLoop(key);
      // Wait a small timeout to let the mock server return IDLE
      setTimeout(() => {
        setTriggeringKey(null);
      }, 5000);
    } catch (err) {
      setTriggeringKey(null);
    }
  };

  const handleAddSkillSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customName.trim() || !customCode.trim()) return;
    
    onAddSkill(customName, customDesc, customCode);
    setCustomName('');
    setCustomDesc('');
    setCustomCode('');
    setIsAdding(false);
  };

  const getLoopBadgeColor = (status: string) => {
    if (status === 'RUNNING') return 'bg-amber-500/10 border-amber-500/30 text-amber-400 font-bold animate-pulse';
    return 'bg-slate-950 border-slate-800 text-slate-500 font-normal';
  };

  return (
    <div id="autonomous-loops-panel" className="space-y-6">
      
      {/* Visual Header Grid for Loops Triggering */}
      <div id="loops-grid-header" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Loop: Nightly Market Scan */}
        <div className="bg-slate-950/45 border border-white/5 p-4.5 rounded-sm flex flex-col justify-between h-[160px] shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div className="flex items-start justify-between">
            <div className="space-y-0.5">
              <span className="text-[9px] text-cyan-400 font-mono font-bold tracking-widest uppercase">Macro Job #1</span>
              <h3 className="text-xs font-bold font-mono text-slate-205">Nightly Market Scan</h3>
            </div>
            <span className={`text-[8px] font-mono px-2 py-0.5 border rounded-sm uppercase ${getLoopBadgeColor(loops.nightlyMarketScan.status)}`}>
              {loops.nightlyMarketScan.status}
            </span>
          </div>

          <p className="text-[10px] text-slate-450 font-mono leading-normal line-clamp-3">
            Outcome: {loops.nightlyMarketScan.outcome}
          </p>

          <button
            onClick={() => handleTrigger('nightlyMarketScan')}
            disabled={triggeringKey !== null}
            className="w-full text-[10px] font-mono bg-slate-900/40 hover:bg-cyan-500/10 hover:border-cyan-500/30 active:bg-slate-955 text-cyan-400 border border-white/5 py-1.5 rounded-sm flex items-center justify-center space-x-1 cursor-pointer transition-all disabled:opacity-30 disabled:pointer-events-none mt-2 shadow-[0_0_6px_rgba(6,182,212,0.05)]"
          >
            <Play className="w-3 h-3 text-emerald-400 shrink-0" />
            <span>{loops.nightlyMarketScan.status === 'RUNNING' ? 'SCANNING...' : 'TRIGGER JOB'}</span>
          </button>
        </div>

        {/* Loop: Skill Auto Creation */}
        <div className="bg-slate-955/45 border border-white/5 p-4.5 rounded-sm flex flex-col justify-between h-[160px] shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div className="flex items-start justify-between">
            <div className="space-y-0.5">
              <span className="text-[9px] text-cyan-400 font-mono font-bold tracking-widest uppercase">Macro Job #2</span>
              <h3 className="text-xs font-bold font-mono text-slate-205">Skill Auto-Evolution</h3>
            </div>
            <span className={`text-[8px] font-mono px-2 py-0.5 border rounded-sm uppercase ${getLoopBadgeColor(loops.skillAutoCreation.status)}`}>
              {loops.skillAutoCreation.status}
            </span>
          </div>

          <p className="text-[10px] text-slate-450 font-mono leading-normal line-clamp-3">
            Outcome: {loops.skillAutoCreation.outcome}
          </p>

          <button
            onClick={() => handleTrigger('skillAutoCreation')}
            disabled={triggeringKey !== null}
            className="w-full text-[10px] font-mono bg-slate-900/40 hover:bg-cyan-500/10 hover:border-cyan-500/30 active:bg-slate-955 text-cyan-400 border border-white/5 py-1.5 rounded-sm flex items-center justify-center space-x-1 cursor-pointer transition-all disabled:opacity-30 disabled:pointer-events-none mt-2 shadow-[0_0_6px_rgba(6,182,212,0.05)]"
          >
            <Cpu className="w-3 h-3 text-cyan-400 shrink-0 animate-spin" />
            <span>{loops.skillAutoCreation.status === 'RUNNING' ? 'EVOLVING...' : 'CODE DEVELOPMENT'}</span>
          </button>
        </div>

        {/* Loop: Paper Trade Review */}
        <div className="bg-slate-955/45 border border-white/5 p-4.5 rounded-sm flex flex-col justify-between h-[160px] shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div className="flex items-start justify-between">
            <div className="space-y-0.5">
              <span className="text-[9px] text-cyan-400 font-mono font-bold tracking-widest uppercase">Macro Job #3</span>
              <h3 className="text-xs font-bold font-mono text-slate-205">Paper Trade Review</h3>
            </div>
            <span className={`text-[8px] font-mono px-2 py-0.5 border rounded-sm uppercase ${getLoopBadgeColor(loops.paperTradeReview.status)}`}>
              {loops.paperTradeReview.status}
            </span>
          </div>

          <p className="text-[10px] text-slate-450 font-mono leading-normal line-clamp-3">
            Outcome: {loops.paperTradeReview.outcome}
          </p>

          <button
            onClick={() => handleTrigger('paperTradeReview')}
            disabled={triggeringKey !== null}
            className="w-full text-[10px] font-mono bg-slate-900/40 hover:bg-cyan-500/10 hover:border-cyan-500/30 active:bg-slate-955 text-cyan-400 border border-white/5 py-1.5 rounded-sm flex items-center justify-center space-x-1 cursor-pointer transition-all disabled:opacity-30 disabled:pointer-events-none mt-2 shadow-[0_0_6px_rgba(6,182,212,0.05)]"
          >
            <RefreshCw className="w-3 h-3 text-cyan-455 shrink-0" />
            <span>{loops.paperTradeReview.status === 'RUNNING' ? 'EVALUATING...' : 'P&L REPORT SCAN'}</span>
          </button>
        </div>

        {/* Loop: Hypothesis R&D */}
        <div className="bg-slate-955/45 border border-white/5 p-4.5 rounded-sm flex flex-col justify-between h-[160px] shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div className="flex items-start justify-between">
            <div className="space-y-0.5">
              <span className="text-[9px] text-cyan-400 font-mono font-bold tracking-widest uppercase">Macro Job #4</span>
              <h3 className="text-xs font-bold font-mono text-slate-205">Hypothesis R&D</h3>
            </div>
            <span className={`text-[8px] font-mono px-2 py-0.5 border rounded-sm uppercase ${getLoopBadgeColor(loops.hypothesisRandD.status)}`}>
              {loops.hypothesisRandD.status}
            </span>
          </div>

          <p className="text-[10px] text-slate-450 font-mono leading-normal line-clamp-3">
            Outcome: {loops.hypothesisRandD.outcome}
          </p>

          <button
            onClick={() => handleTrigger('hypothesisRandD')}
            disabled={triggeringKey !== null}
            className="w-full text-[10px] font-mono bg-slate-900/40 hover:bg-cyan-500/10 hover:border-cyan-500/30 active:bg-slate-955 text-cyan-400 border border-white/5 py-1.5 rounded-sm flex items-center justify-center space-x-1 cursor-pointer transition-all disabled:opacity-30 disabled:pointer-events-none mt-2 shadow-[0_0_6px_rgba(6,182,212,0.05)]"
          >
            <Sparkles className="w-3 h-3 text-cyan-400 shrink-0" />
            <span>{loops.hypothesisRandD.status === 'RUNNING' ? 'SIMULATING...' : 'R&D BACKTESTS'}</span>
          </button>
        </div>
      </div>

      {/* Main Splits: AI-Crafted Skills Code Explorer */}
      <div id="skills-code-split" className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left list panel */}
        <div className="lg:col-span-1 bg-slate-955/45 border border-white/5 rounded-sm p-4 flex flex-col h-[400px] shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          <div className="flex items-center justify-between pb-2.5 border-b border-white/5 mb-3 shrink-0">
            <div className="flex items-center space-x-1.5">
              <Code2 className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider">Self-Evolved Skills</span>
            </div>
            <button
              onClick={() => setIsAdding(!isAdding)}
              className="text-[10px] font-mono text-cyan-455 hover:text-cyan-355 cursor-pointer"
            >
              {isAdding ? '[COMPILE CANCEL]' : '[WRITE SKILL]'}
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2">
            {skills.map(skill => (
              <button
                id={`skill-btn-${skill.name.replace(/\./g, '-')}`}
                key={skill.name}
                onClick={() => { setSelectedSkill(skill); setIsAdding(false); }}
                className={`w-full text-left p-3 rounded-sm border transition-all cursor-pointer flex flex-col justify-between ${
                  selectedSkill?.name === skill.name && !isAdding
                    ? 'bg-cyan-500/10 border-cyan-500/35 text-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.08)]'
                    : 'bg-slate-900/10 border-white/5 text-slate-400 hover:border-slate-800 hover:bg-slate-900/20'
                }`}
              >
                <div>
                  <h4 className="text-xs font-bold font-mono text-slate-200 truncate">{skill.name}</h4>
                  <p className="text-[10px] font-sans text-slate-500 line-clamp-1 truncate">{skill.description}</p>
                </div>
                <div className="flex items-center justify-between text-[9px] font-mono mt-2 pt-1 border-t border-white/5 w-full text-slate-500">
                  <span>Success WR: <strong className="text-emerald-400">{skill.successRate}%</strong></span>
                  <span>Runs: {skill.usageCount}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Right Code Display Viewer */}
        <div className="lg:col-span-2 bg-slate-950/20 border border-white/5 rounded-sm p-5 flex flex-col h-[400px] shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
          {isAdding ? (
            <form onSubmit={handleAddSkillSubmit} className="flex-1 flex flex-col justify-between">
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4 shrink-0">
                  <div>
                    <label className="block text-[8px] text-slate-500 font-mono uppercase mb-1">Skill Script Path</label>
                    <input
                      type="text"
                      required
                      className="w-full bg-slate-950 border border-white/5 rounded-sm p-2 text-xs text-slate-100 font-mono outline-none focus:border-cyan-500/40 transition-colors"
                      placeholder="e.g. skill_volatility_gate.py"
                      value={customName}
                      onChange={(e) => setCustomName(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-[8px] text-slate-500 font-mono uppercase mb-1">Description</label>
                    <input
                      type="text"
                      className="w-full bg-slate-950 border border-white/5 rounded-sm p-2 text-xs text-slate-100 font-mono outline-none focus:border-cyan-500/40 transition-colors"
                      placeholder="Filters trade triggers based on ATR standard deviations"
                      value={customDesc}
                      onChange={(e) => setCustomDesc(e.target.value)}
                    />
                  </div>
                </div>

                <div className="flex-1 flex flex-col min-h-[160px]">
                  <label className="block text-[8px] text-slate-500 font-mono uppercase mb-1 shrink-0">Python Algorithm Code</label>
                  <textarea
                    required
                    className="flex-1 w-full bg-slate-950 border border-white/5 rounded-sm p-3 text-xs text-slate-100 font-mono outline-none resize-none focus:border-cyan-500/40 transition-colors"
                    placeholder="def compute_filter(data):\n    return True"
                    value={customCode}
                    onChange={(e) => setCustomCode(e.target.value)}
                  />
                </div>
              </div>

              <div className="flex justify-end pt-2 shrink-0">
                <button
                  type="submit"
                  className="bg-slate-900/40 border border-white/5 hover:border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 active:bg-slate-950 text-xs font-mono py-2 px-6 rounded-sm flex items-center space-x-1 cursor-pointer transition-all shadow-[0_0_6px_rgba(6,182,212,0.05)]"
                >
                  <CheckCircle className="w-3.5 h-3.5" />
                  <span>COMPILE DEVELOPED SKILL</span>
                </button>
              </div>
            </form>
          ) : selectedSkill ? (
            <div className="flex flex-col justify-between h-full">
              <div className="space-y-3 shrink-0 border-b border-white/5 pb-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-cyan-400 font-mono">{selectedSkill.name}</h3>
                  <span className="text-[9px] text-slate-500 font-mono">Self-Written on: {new Date(selectedSkill.lastUpdated).toLocaleDateString()}</span>
                </div>
                <p className="text-[11px] text-slate-300 font-sans">{selectedSkill.description}</p>
              </div>

              <div className="flex-1 bg-slate-950/40 p-4 rounded-sm border border-white/5 my-3 font-mono text-[11px] leading-relaxed text-slate-350 overflow-y-auto select-text whitespace-pre relative">
                <div className="absolute right-3 top-3 text-[8px] text-slate-600 uppercase font-black tracking-widest bg-slate-950 px-2 py-1 rounded-sm border border-white/5">
                  Python 3.11 Compliance Inside Docker
                </div>
                {selectedSkill.code}
              </div>

              <div className="flex items-center space-x-4 pt-1 text-[9px] text-slate-500 font-mono shrink-0">
                <span className="flex items-center space-x-1">
                  <Play className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Interactive execution status: <strong className="text-emerald-400 font-bold">READY</strong></span>
                </span>
                <span>Times Called: {selectedSkill.usageCount} sweeps</span>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500 font-mono text-xs">
              <Terminal className="w-8 h-8 text-slate-755 mb-1" />
              <p>Select a Python skill code algorithm to view compiler output.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
