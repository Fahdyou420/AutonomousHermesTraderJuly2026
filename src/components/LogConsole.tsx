import React, { useEffect, useRef } from 'react';
import { Activity } from 'lucide-react';

interface LogConsoleProps {
  logs: any[];
}

export default function LogConsole({ logs }: LogConsoleProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const getLogLevelColor = (level: string) => {
    switch (level) {
      case 'SUCCESS': return 'text-emerald-450';
      case 'WARNING': return 'text-amber-500';
      case 'ERROR': return 'text-rose-500';
      default: return 'text-cyan-400';
    }
  };

  return (
    <div className="flex flex-col h-[600px] bg-[#05070a] border border-white/10 rounded overflow-hidden">
      <div className="bg-slate-900/40 p-3 border-b border-white/10 flex items-center space-x-2">
        <Activity className="w-4 h-4 text-cyan-400 animate-pulse" />
        <span className="text-[11px] font-mono font-bold tracking-widest text-slate-300 uppercase">
          Live System & LLM Logs
        </span>
      </div>
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-[10px] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900/20 to-black"
      >
        {logs.map((log) => (
          <div key={log.id} className="border-b border-white/5 pb-2 mb-2 last:border-0 hover:bg-white/[0.02] p-1 transition-colors rounded">
            <div className="flex items-center space-x-3 mb-1">
              <span className="text-slate-500">{new Date(log.timestamp).toLocaleTimeString()}</span>
              <span className={`font-bold uppercase ${getLogLevelColor(log.level)}`}>[{log.level}]</span>
              <span className="text-amber-500/70">{log.source}</span>
            </div>
            <div className="text-slate-300 pl-4 whitespace-pre-wrap leading-relaxed">
              {log.text}
            </div>
          </div>
        ))}
        {logs.length === 0 && (
          <div className="text-slate-500 italic text-center mt-10">Waiting for events...</div>
        )}
      </div>
    </div>
  );
}
