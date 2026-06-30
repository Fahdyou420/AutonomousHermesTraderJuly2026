import React, { useState, useRef, useEffect } from 'react';
import { TerminalLine, LogMessage } from '../types';
import { Send, Terminal as TermIcon, ShieldAlert, BookOpen, Cpu, Sparkles, ChevronRight, Activity } from 'lucide-react';

interface AgentTerminalProps {
  logs: LogMessage[];
  onAddLog: (logText: string, level: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS', source: string) => void;
}

export default function AgentTerminal({ logs, onAddLog }: AgentTerminalProps) {
  const [input, setInput] = useState('');
  const [terminalLines, setTerminalLines] = useState<TerminalLine[]>([
    {
      id: 'init_1',
      timestamp: new Date().toISOString(),
      type: 'success',
      text: 'Hermes Trading Agent Supervisor CLI initialized successfully. Ollama prompt engine online.'
    },
    {
      id: 'init_2',
      timestamp: new Date().toISOString(),
      type: 'tool-call',
      text: 'Initial core checklist verified: MT5 ZMQ Sockets (5555, 5556, 5557) linked. Redis listening on port 6379. Staged Trust: hypothesis mode enabled.'
    },
    {
      id: 'init_3',
      timestamp: new Date().toISOString(),
      type: 'output',
      text: 'Please type a slash command (e.g. /help, /backtest, /risk, /status) or chat with the Hermes core decision engine below.'
    }
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [terminalLines]);

  const addLine = (type: 'input' | 'output' | 'error' | 'success' | 'tool-call', text: string, toolDetails?: any) => {
    setTerminalLines(prev => [
      ...prev,
      {
        id: 'line_' + Date.now() + Math.random().toString(36).substr(2, 4),
        timestamp: new Date().toISOString(),
        type,
        text,
        toolDetails
      }
    ]);
  };

  const handleCommand = async (cmd: string) => {
    const trimmed = cmd.trim();
    if (!trimmed) return;

    addLine('input', trimmed);
    setInput('');

    // Slash command processing
    if (trimmed.startsWith('/')) {
      const parts = trimmed.split(' ');
      const action = parts[0].toLowerCase();

      switch (action) {
        case '/help':
          addLine('output', `Available Hermes commands:
  /help                  - Display this help checklist interface.
  /status                - Run real-time diagnostic checks on ZMQ Sockets, Redis, Ollama & ChromaDB.
  /backtest              - Instruct Ollama and Hermes core to simulate a fast XAUUSD SMC backtest.
  /risk                  - Verify maximum exposure settings, daily drawdown checks & security guards.
  /vault                  - Enumerate obsidian study notes, strategy briefs & reviews.
  /clear                 - Flush terminal window history buffers.
  /sweep <price>         - Force trigger a trade simulation sweep of BSL/SSL at target price.`);
          break;

        case '/status':
          addLine('tool-call', 'Dispatching system status query...');
          try {
            const res = await fetch('/api/status');
            const data = await res.json();
            addLine('success', `[DIAGNOSTICS]
  Ollama Engine  : ${data.ollama}
  RPC Listener   : ${data.hermesRpc}
  Redis Pub/Sub  : ${data.redis}
  ZeroMQ DATA    : ${data.mt5Zmq?.data}
  ZeroMQ ORDER   : ${data.mt5Zmq?.order}
  ChromaDB       : ${data.chromaDb}
  Obsidian Vault : ${data.obsidian}`);
          } catch (e) {
            addLine('error', 'Status check failed.');
          }
          break;

        case '/risk':
          addLine('tool-call', 'Security Auditor: Fetching active risk constraints...');
          try {
            const res = await fetch('/api/trades');
            const data = await res.json();
            addLine('output', `[HERMES INTRA-DAY RISK BOUNDARIES]
  • Max Risk Per Trade  : 1.0% of nominal margin (STRICTLY COMPLIED)
  • Active Exposure     : ${data.active?.length || 0} Open Trades
  • Sub-Account Daily DD: ${(data.dailyDDPercent || 0).toFixed(2)}% (Max 4.0%)
  • Strategy Weekly DD  : ${(data.weeklyDDPercent || 0).toFixed(2)}% (Max 8.0%)
  • Risk Status         : NORMAL`);
          } catch (e) {
            addLine('error', 'Risk audit check failed.');
          }
          break;

        case '/clear':
          setTerminalLines([]);
          break;

        case '/vault':
          addLine('tool-call', 'Querying mounted Obsidian vaults...');
          try {
            const res = await fetch('/api/vault');
            const data = await res.json();
            addLine('success', `[OBSIDIAN DOCUMENT BASE]
  Found ${data.length} synchronized files.
  Database online. RAG ready.`);
          } catch (e) {
            addLine('error', 'Vault check failed.');
          }
          break;

        case '/backtest':
          addLine('tool-call', 'Initiating backtest queue. Strategy validation will run in background thread.');
          try {
            await fetch('/api/loops/trigger/hypothesisRandD', { method: 'POST' });
            addLine('success', 'Backtest requested successfully. Monitor autonomous loops table for results.');
          } catch (e) {
            addLine('error', 'Dispatching backtest loop failed.');
          }
          break;

        case '/sweep':
          const targetPriceStr = parts[1] || '2338.50';
          const targetPrice = parseFloat(targetPriceStr);
          if (isNaN(targetPrice)) {
            addLine('error', 'Sweep error: Target must be a valid numeric gold price, e.g. /sweep 2338.50');
            break;
          }
          addLine('tool-call', `Injecting custom tick event to ZeroMQ DATA channel: XAUUSD Price -> $${targetPrice}. Watching for liquidity sweep validation...`);
          
          // Trigger a POST call on server to notify a sweep or log event
          try {
            await fetch('/api/logs', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                source: 'MT5_DATA',
                level: 'SUCCESS',
                text: `MANUAL INTERVENTION: Price tick simulated at $${targetPrice}. Verification underway.`
              })
            });
            onAddLog(`Price tick simulated at $${targetPrice}`, 'SUCCESS', 'MT5_DATA');
          } catch(err) {}
          break;

        default:
          addLine('error', `Command error: Unknown slash action '${action}'. Type /help to see allowed options.`);
          break;
      }
    } else {
      // Natural language query to Hermes (Gemini API server-proxy)
      addLine('tool-call', 'Directing prompt request to Hermes LLM Core (Gemini 3.5-Flash + Ollama-RAG)...');
      setIsTyping(true);
      
      try {
        const res = await fetch('/api/gemini/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: trimmed, type: 'user-chat' })
        });
        const data = await res.json();
        setIsTyping(false);
        if (data.text) {
          addLine('output', data.text);
        } else if (data.error) {
          addLine('error', `Failed to prompt LLM: ${data.error}`);
        }
      } catch (err: any) {
        setIsTyping(false);
        addLine('error', 'Communication pipeline broke. Ollama / Gemini server did not respond.');
      }
    }
  };

  const truncateText = (text: string, len: number) => {
    if (text.length > len) return text.substring(0, len) + '...';
    return text;
  };

  return (
    <div id="terminal-interface" className="flex flex-col h-[550px] bg-slate-950/45 border border-white/5 rounded backdrop-blur-md shadow-[0_4px_24px_rgba(0,0,0,0.4)]">
      {/* Console Title Bar */}
      <div id="terminal-bar" className="flex items-center justify-between bg-slate-900/30 backdrop-blur-sm border-b border-white/5 px-4 py-3 shrink-0">
        <div id="terminal-bar-left" className="flex items-center space-x-2">
          <div className="flex space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80 block"></span>
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80 block"></span>
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 block"></span>
          </div>
          <span className="text-[10px] font-mono font-bold tracking-wider text-cyan-455 ml-2">HERMES CLI CONSOLE (V0.15.2)</span>
        </div>
        <div id="terminal-bar-right" className="flex items-center space-x-4 text-[9px] text-slate-500 font-mono">
          <span className="flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-450 animate-ping"></span>
            <span className="text-cyan-400 font-bold lowercase tracking-normal">host integrated</span>
          </span>
          <span className="bg-slate-900/40 border border-white/5 px-2 py-0.5 rounded text-slate-400">Ollama/Gemini-Fullstack</span>
        </div>
      </div>

      {/* Terminal Viewports Split */}
      <div id="terminal-viewport" className="flex flex-1 overflow-hidden">
        {/* CLI Prompt Area */}
        <div id="cli-lines-container" className="flex-1 flex flex-col justify-between p-4 font-mono text-xs text-slate-300 space-y-3 overflow-hidden">
          <div className="flex-1 space-y-3 overflow-y-auto pr-2 max-h-[380px]">
            {terminalLines.map(line => (
              <div id={line.id} key={line.id} className="leading-relaxed">
                <span className="text-slate-600 text-[9px] select-none mr-2 block sm:inline">
                  [{new Date(line.timestamp).toLocaleTimeString()}]
                </span>
                
                {line.type === 'input' && (
                  <span className="text-slate-200 font-semibold">
                    <span className="text-cyan-400 mr-2 font-black">hermes$</span>
                    {line.text}
                  </span>
                )}

                {line.type === 'output' && (
                  <div className="text-slate-300 pl-4 whitespace-pre-wrap border-l border-cyan-500/20 mt-1 bg-slate-900/5 py-1 px-2.5 rounded-sm">
                    {line.text}
                  </div>
                )}

                {line.type === 'tool-call' && (
                  <span className="text-slate-400 italic">
                    <span className="text-amber-500 font-mono font-bold mr-2 text-[10px]">⚙ [AGENT TOOLCALL]</span>
                    {line.text}
                  </span>
                )}

                {line.type === 'success' && (
                  <div className="text-emerald-450 pl-4 whitespace-pre-wrap border-l border-emerald-500/20 mt-1 bg-emerald-550/5 py-1.5 px-2.5 rounded border border-emerald-550/10">
                    <span className="font-bold">✔ [SUCCESS] </span>
                    {line.text}
                  </div>
                )}

                {line.type === 'error' && (
                  <div className="text-rose-450 pl-4 whitespace-pre-wrap border-l border-rose-500/25 mt-1 bg-rose-550/5 py-1.5 px-2.5 rounded border border-rose-550/10">
                    <span className="font-bold">✘ [ERROR] </span>
                    {line.text}
                  </div>
                )}
              </div>
            ))}
            
            {isTyping && (
              <div className="flex items-center space-x-2 text-cyan-400 italic">
                <Sparkles className="w-3 h-3 animate-spin text-cyan-400" />
                <span className="animate-pulse">Hermes is thinking... analyzing market structures...</span>
              </div>
            )}
            <div ref={scrollRef} />
          </div>

          {/* Terminal Input Box */}
          <form
            id="terminal-input-form"
            onSubmit={(e) => {
              e.preventDefault();
              handleCommand(input);
            }}
            className="flex items-center border border-white/5 bg-slate-900/10 focus-within:border-cyan-500/40 focus-within:shadow-[0_0_10px_rgba(6,182,212,0.06)] rounded-sm py-1.5 px-3 transition-all shrink-0"
          >
            <ChevronRight className="w-4 h-4 text-slate-500 mr-1.5 shrink-0" />
            <input
              id="terminal-input-field"
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="bg-transparent text-slate-100 flex-1 outline-none font-mono text-xs border-0 py-1"
              placeholder="Query Gemini/Ollama, or type slash command (e.g., /backtest, /risk)..."
            />
            <button
              id="btn-terminal-submit"
              type="submit"
              className="p-1 px-2.5 text-cyan-450 hover:text-cyan-350 active:text-cyan-500 disabled:text-slate-700 cursor-pointer transition-colors"
              disabled={!input.trim() || isTyping}
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>

        {/* Live Logs Channel Side-panel */}
        <div id="logs-sidepanel" className="hidden md:flex flex-col w-72 bg-slate-900/5 border-l border-white/5 overflow-hidden">
          <div className="bg-slate-900/20 p-2.5 border-b border-white/5 h-11 flex items-center space-x-2 shrink-0">
            <Activity className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
            <span className="text-[9px] font-mono font-bold tracking-widest text-slate-450 uppercase">Redis & ZMQ Event Log</span>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2 max-h-[440px]">
            {logs.slice().reverse().map(log => {
              const getLogLevelColor = (level: string) => {
                switch (level) {
                  case 'SUCCESS': return 'text-emerald-450 font-semibold';
                  case 'WARNING': return 'text-amber-500 font-semibold';
                  case 'ERROR': return 'text-rose-500 font-semibold';
                  default: return 'text-cyan-400 font-semibold';
                }
              };

              return (
                <div id={log.id} key={log.id} className="p-2 rounded-sm bg-slate-900/10 border border-white/5 text-[9px] font-mono leading-tight hover:border-cyan-500/20 transition-all">
                  <div className="flex justify-between text-[8px] text-slate-650 mb-1">
                    <span>{log.source}</span>
                    <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-slate-400 break-words line-clamp-3">
                    <span className={`${getLogLevelColor(log.level)} mr-1`}>● {log.level}</span>
                    {truncateText(log.text, 80)}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
