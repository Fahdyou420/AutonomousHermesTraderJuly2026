import React from 'react';
import { SystemStatus } from '../types';
import { Server, Cpu, Database, RefreshCw, Layers, CheckCircle, XCircle } from 'lucide-react';

interface StatusCardProps {
  status: SystemStatus;
  onRefresh: () => void;
  loading: boolean;
}

export default function StatusCard({ status, onRefresh, loading }: StatusCardProps) {
  const getStatusIcon = (state: 'connected' | 'disconnected' | 'error') => {
    switch (state) {
      case 'connected':
        return <CheckCircle id="status-icon-connected" className="w-4 h-4 text-emerald-400 shrink-0" />;
      case 'disconnected':
        return <XCircle id="status-icon-disconnected" className="w-4 h-4 text-rose-500 shrink-0" />;
      default:
        return <XCircle id="status-icon-error" className="w-4 h-4 text-amber-500 shrink-0 animate-pulse" />;
    }
  };

  const getStatusText = (state: 'connected' | 'disconnected' | 'error') => {
    switch (state) {
      case 'connected':
        return <span id="status-text-connected" className="text-emerald-400 font-mono text-xs font-semibold bg-emerald-500/10 px-2 py-0.5 rounded-sm border border-emerald-500/20">ONLINE</span>;
      case 'disconnected':
        return <span id="status-text-disconnected" className="text-rose-400 font-mono text-xs font-semibold bg-rose-500/10 px-2 py-0.5 rounded-sm border border-rose-500/20">OFFLINE</span>;
      default:
        return <span id="status-text-error" className="text-amber-400 font-mono text-xs font-semibold bg-amber-500/10 px-2 py-0.5 rounded-sm border border-amber-500/20 animate-pulse">ERROR</span>;
    }
  };

  return (
    <div id="status-control-panel" className="bg-slate-950/45 border border-white/5 rounded backdrop-blur-md p-5 shadow-[0_4px_24px_rgba(0,0,0,0.4)]">
      <div id="status-header" className="flex items-center justify-between mb-4">
        <div id="status-title-container" className="flex items-center space-x-2">
          <Layers id="layers-icon" className="w-4 h-4 text-cyan-400" />
          <h2 id="status-panel-title" className="text-xs font-bold tracking-widest text-slate-400 uppercase font-mono">
            Middleware & Sockets (Layer 1-3)
          </h2>
        </div>
        <button
          id="btn-refresh-status"
          onClick={onRefresh}
          className="p-1 px-3 text-[10px] bg-slate-900/40 hover:bg-cyan-500/15 active:bg-slate-950 border border-white/5 hover:border-cyan-500/30 text-slate-300 font-mono rounded-sm flex items-center space-x-1.5 transition-all cursor-pointer shadow-[0_0_6px_rgba(6,182,212,0.05)]"
          disabled={loading}
        >
          <RefreshCw id="refresh-icon" className={`w-3 h-3 text-cyan-400 ${loading ? 'animate-spin' : ''}`} />
          <span>{loading ? 'SYNCING...' : 'POLL'}</span>
        </button>
      </div>

      <div id="status-grid" className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
        {/* Ollama LLM */}
        <div id="status-item-ollama" className="bg-slate-900/10 border border-white/5 p-3 rounded-sm flex flex-col justify-between min-h-[90px] hover:border-cyan-500/30 hover:shadow-[0_0_10px_rgba(6,182,212,0.06)] transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400 text-[10px] font-mono font-semibold uppercase tracking-wider">Ollama LLM</span>
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="flex flex-col space-y-1">
            <span className="text-[9px] text-slate-500 font-mono break-all leading-tight">host.docker.internal:11434</span>
            <div className="flex items-center space-x-1.5 mt-1">
              {getStatusIcon(status.ollama)}
              {getStatusText(status.ollama)}
            </div>
          </div>
        </div>

        {/* Redis Pub/Sub */}
        <div id="status-item-redis" className="bg-slate-900/10 border border-white/5 p-3 rounded-sm flex flex-col justify-between min-h-[90px] hover:border-cyan-500/30 hover:shadow-[0_0_10px_rgba(6,182,212,0.06)] transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400 text-[10px] font-mono font-semibold uppercase tracking-wider">Redis Pub/Sub</span>
            <Database className="w-3.5 h-3.5 text-red-400" />
          </div>
          <div className="flex flex-col space-y-1">
            <span className="text-[9px] text-slate-500 font-mono break-all leading-tight">redis://redis:6379</span>
            <div className="flex items-center space-x-1.5 mt-1">
              {getStatusIcon(status.redis)}
              {getStatusText(status.redis)}
            </div>
          </div>
        </div>

        {/* ChromaDB Vector */}
        <div id="status-item-chromadb" className="bg-slate-900/10 border border-white/5 p-3 rounded-sm flex flex-col justify-between min-h-[90px] hover:border-cyan-500/30 hover:shadow-[0_0_10px_rgba(6,182,212,0.06)] transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400 text-[10px] font-mono font-semibold uppercase tracking-wider">ChromaDB</span>
            <Database className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="flex flex-col space-y-1">
            <span className="text-[9px] text-slate-500 font-mono break-all leading-tight">http://chromadb:8000</span>
            <div className="flex items-center space-x-1.5 mt-1">
              {getStatusIcon(status.chromaDb)}
              {getStatusText(status.chromaDb)}
            </div>
          </div>
        </div>

        {/* Obsidian Vault */}
        <div id="status-item-obsidian" className="bg-slate-900/10 border border-white/5 p-3 rounded-sm flex flex-col justify-between min-h-[90px] hover:border-cyan-500/30 hover:shadow-[0_0_10px_rgba(6,182,212,0.06)] transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400 text-[10px] font-mono font-semibold uppercase tracking-wider">Obsidian Vault</span>
            <Layers className="w-3.5 h-3.5 text-purple-400" />
          </div>
          <div className="flex flex-col space-y-1">
            <span className="text-[9px] text-slate-500 font-mono break-all leading-tight">/data/obsidian</span>
            <div className="flex items-center space-x-1.5 mt-1">
              {getStatusIcon(status.obsidian)}
              {getStatusText(status.obsidian)}
            </div>
          </div>
        </div>

        {/* Hermes Host RPC */}
        <div id="status-item-rpc" className="bg-slate-900/10 border border-white/5 p-3 rounded-sm flex flex-col justify-between min-h-[90px] hover:border-cyan-500/30 hover:shadow-[0_0_10px_rgba(6,182,212,0.06)] transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400 text-[10px] font-mono font-semibold uppercase tracking-wider">Hermes Host RPC</span>
            <Server className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="flex flex-col space-y-1">
            <span className="text-[9px] text-slate-500 font-mono break-all leading-tight">host.docker.internal:7778</span>
            <div className="flex items-center space-x-1.5 mt-1">
              {getStatusIcon(status.hermesRpc)}
              {getStatusText(status.hermesRpc)}
            </div>
          </div>
        </div>

        {/* MetaTrader 5 Bridge */}
        <div id="status-item-mt5" className="bg-slate-900/10 border border-white/5 p-3 rounded-sm flex flex-col justify-between min-h-[90px] hover:border-cyan-500/30 hover:shadow-[0_0_10px_rgba(6,182,212,0.06)] transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400 text-[10px] font-mono font-semibold uppercase tracking-wider">MT5 ZMQ Bridge</span>
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="flex flex-col space-y-1">
            <div className="flex items-center justify-between text-[8px] text-slate-500 font-mono">
              <span>DATA: 5555</span>
              <span className="text-cyan-400">OK</span>
            </div>
            <div className="flex items-center justify-between text-[8px] text-slate-500 font-mono">
              <span>DRAW: 5556</span>
              <span className="text-cyan-400">OK</span>
            </div>
            <div className="flex items-center justify-between text-[8px] text-slate-500 font-mono">
              <span>ORDER: 5557</span>
              <span className="text-cyan-400">OK</span>
            </div>
            <div className="flex items-center space-x-1.5 mt-1">
              {getStatusIcon(status.mt5Zmq.order)}
              {getStatusText(status.mt5Zmq.order)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
