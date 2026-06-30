import React, { useState, useEffect } from 'react';
import { ObsidianNote, ChromaDocument } from '../types';
import { FileText, Database, Plus, Search, HelpCircle, Tag, Clock, Check } from 'lucide-react';

interface KnowledgeExplorerProps {
  notes: ObsidianNote[];
  onAddNote: (title: string, content: string, folder: 'Strategy Cards' | 'Trade Logs' | 'Market Studies' | 'Hypotheses', tags: string[]) => void;
}

export default function KnowledgeExplorer({ notes, onAddNote }: KnowledgeExplorerProps) {
  const [activeTab, setActiveTab] = useState<'obsidian' | 'chromadb'>('obsidian');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNote, setSelectedNote] = useState<ObsidianNote | null>(null);
  
  // Custom Create Note form open state
  const [isCreating, setIsCreating] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newFolder, setNewFolder] = useState<'Strategy Cards' | 'Trade Logs' | 'Market Studies' | 'Hypotheses'>('Strategy Cards');
  const [newTagsStr, setNewTagsStr] = useState('');
  
  // ChromaDB Vector Search results mock configuration
  const [chromaResults, setChromaResults] = useState<ChromaDocument[]>([]);
  const [chromaLoading, setChromaLoading] = useState(false);
  const [chromaQuery, setChromaQuery] = useState('XAUUSD SMC strategy');

  const fetchChromaResults = async (query: string) => {
    if (!query.trim()) return;
    setChromaLoading(true);
    try {
      const res = await fetch('/api/vault/search?q=' + encodeURIComponent(query));
      const data = await res.json();
      if (Array.isArray(data)) {
        setChromaResults(data.map((item: any, idx: number) => ({
          id: item.path || `doc_${idx}`,
          text: item.excerpt || item.content || '',
          metadata: { source: item.path, stage: '', timestamp: '' },
          distance: 0
        })));
      }
    } catch (e) {
      setChromaResults([]);
    } finally {
      setChromaLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'chromadb') {
      fetchChromaResults(chromaQuery);
    }
  }, [activeTab]);

  useEffect(() => {
    if (notes.length > 0 && !selectedNote) {
      setSelectedNote(notes[0]);
    }
  }, [notes, selectedNote]);

  const filteredNotes = notes.filter(n => 
    n.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
    n.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
    n.tags.some(t => t.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const filteredChroma = chromaResults.filter(doc =>
    doc.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
    doc.metadata.source.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSubmitNote = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newContent.trim()) return;

    const tags = newTagsStr.split(',').map(t => t.trim()).filter(Boolean);
    onAddNote(newTitle, newContent, newFolder, tags);
    
    // Reset form
    setNewTitle('');
    setNewContent('');
    setNewTagsStr('');
    setIsCreating(false);
  };

  return (
    <div id="knowledge-explorer-panel" className="bg-slate-950/45 border border-white/5 rounded backdrop-blur-md overflow-hidden flex flex-col h-[550px] shadow-[0_4px_24px_rgba(0,0,0,0.4)]">
      {/* Search Header */}
      <div id="explorer-header" className="bg-slate-900/30 backdrop-blur-sm border-b border-white/5 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
        <div id="explorer-tab-container" className="flex items-center space-x-2 bg-slate-950/60 p-1 rounded border border-white/5 shadow-inner">
          <button
            id="tab-btn-obsidian"
            onClick={() => { setActiveTab('obsidian'); setSelectedNote(notes[0] || null); }}
            className={`flex items-center space-x-1.5 py-1.5 px-3 rounded text-[11px] font-mono transition-all cursor-pointer ${
              activeTab === 'obsidian' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/35 shadow-[0_0_8px_rgba(6,182,212,0.1)] font-semibold' : 'text-slate-400 hover:text-slate-205 hover:bg-slate-900/10'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Obsidian Vault</span>
          </button>
          
          <button
            id="tab-btn-chromadb"
            onClick={() => { setActiveTab('chromadb'); }}
            className={`flex items-center space-x-1.5 py-1.5 px-3 rounded text-[11px] font-mono transition-all cursor-pointer ${
              activeTab === 'chromadb' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/35 shadow-[0_0_8px_rgba(6,182,212,0.1)] font-semibold' : 'text-slate-400 hover:text-slate-205 hover:bg-slate-900/10'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>ChromaDB Vector Store</span>
          </button>
        </div>

        {/* Global Finder bar */}
        <div className="flex items-center space-x-2 max-w-sm w-full">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              id="explorer-search"
              type="text"
              className="w-full bg-slate-950 text-xs text-slate-100 placeholder-slate-500 rounded pl-9 pr-3 py-2 border border-white/5 outline-none focus:border-cyan-500/40 font-mono transition-colors h-9"
              placeholder={activeTab === 'obsidian' ? 'FTS5 Full-Text Vault Search...' : 'Semantic Vector Queries...'}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          {activeTab === 'obsidian' && (
            <button
              id="btn-add-vault-note"
              onClick={() => setIsCreating(true)}
              className="bg-slate-900/40 hover:bg-cyan-500/15 active:bg-slate-950 text-xs border border-white/5 hover:border-cyan-500/30 text-cyan-400 p-2.5 rounded font-mono flex items-center space-x-1 cursor-pointer transition-all shrink-0 h-9 shrink-0 shadow-[0_0_6px_rgba(6,182,212,0.05)]"
              title="Compile Study Note"
            >
              <Plus className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Main Content Pane */}
      <div id="explorer-content-container" className="flex-1 flex overflow-hidden">
        {/* Creating / Compiling Note Overlap Panel */}
        {isCreating && activeTab === 'obsidian' ? (
          <div id="compilation-form" className="flex-1 overflow-y-auto p-5 bg-slate-950 flex flex-col">
            <div className="flex justify-between items-center pb-4 border-b border-slate-850 mb-4 shrink-0">
              <h3 className="text-sm font-bold text-slate-200 font-mono uppercase tracking-wider">Compile Strategy Note to Obsidian Vault</h3>
              <button
                onClick={() => setIsCreating(false)}
                className="text-xs text-slate-400 hover:text-slate-200 font-mono"
              >
                [CANCEL]
              </button>
            </div>
            
            <form onSubmit={handleSubmitNote} className="flex-1 flex flex-col space-y-4">
              <div className="grid grid-cols-2 gap-4 shrink-0">
                <div>
                  <label className="block text-[10px] text-slate-400 font-mono uppercase mb-1">Note Title</label>
                  <input
                    type="text"
                    required
                    className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-xs text-slate-100 font-mono outline-none focus:border-indigo-500"
                    placeholder="e.g. London Close Killzone Setup"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 font-mono uppercase mb-1">Vault Folder</label>
                  <select
                    className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-xs text-slate-100 font-mono outline-none focus:border-indigo-500"
                    value={newFolder}
                    onChange={(e) => setNewFolder(e.target.value as any)}
                  >
                    <option value="Strategy Cards">Strategy Cards</option>
                    <option value="Trade Logs">Trade Logs</option>
                    <option value="Market Studies">Market Studies</option>
                    <option value="Hypotheses">Hypotheses</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[10px] text-slate-400 font-mono uppercase mb-1">Tags (Comma Separated)</label>
                <input
                  type="text"
                  className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-xs text-slate-100 font-mono outline-none focus:border-indigo-500"
                  placeholder="SMC, Gold, London, Breakout"
                  value={newTagsStr}
                  onChange={(e) => setNewTagsStr(e.target.value)}
                />
              </div>

              <div className="flex-1 flex flex-col min-h-[160px]">
                <label className="block text-[10px] text-slate-400 font-mono uppercase mb-1 shrink-0">Markdown Content</label>
                <textarea
                  required
                  className="flex-1 w-full bg-slate-900 border border-slate-800 rounded p-3 text-xs text-slate-100 font-mono outline-none focus:border-indigo-500 resize-none"
                  placeholder="# Enter your rules, lessons, displacement triggers..."
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                />
              </div>

              <div className="flex justify-end pt-2 shrink-0">
                <button
                  type="submit"
                  className="bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-slate-100 text-xs font-mono py-2 px-6 rounded flex items-center space-x-1 cursor-pointer transition-colors"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>COMPILE NOTE</span>
                </button>
              </div>
            </form>
          </div>
        ) : (
          <>
            {/* Split View Left Sidebar */}
            <div id="explorer-sidebar" className="w-72 border-r border-white/5 flex flex-col bg-slate-950/20 select-none overflow-y-auto">
              {activeTab === 'obsidian' ? (
                <div className="p-3 space-y-1">
                  {filteredNotes.map(note => (
                    <button
                      id={`sidebar-note-${note.path.replace(/[^a-zA-Z0-9]/g, '-')}`}
                      key={note.path}
                      onClick={() => setSelectedNote(note)}
                      className={`w-full text-left p-2.5 rounded-sm text-xs font-mono flex items-start space-x-2 transition-all cursor-pointer ${
                        selectedNote?.path === note.path ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-[0_0_8px_rgba(6,182,212,0.06)]' : 'text-slate-400 hover:bg-slate-900/30 border border-transparent hover:text-slate-200'
                      }`}
                    >
                      <FileText className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${selectedNote?.path === note.path ? 'text-cyan-400' : 'text-slate-600'}`} />
                      <div className="overflow-hidden">
                        <p className="font-semibold truncate">{note.title}</p>
                        <span className="text-[9px] text-slate-500 block truncate">{note.path}</span>
                      </div>
                    </button>
                  ))}
                  {filteredNotes.length === 0 && (
                    <p className="text-xs text-slate-500 p-4 text-center">No notes found matching query</p>
                  )}
                </div>
              ) : (
                <div className="p-3 space-y-2">
                  <div className="p-2.5 border border-white/5 rounded-sm bg-cyan-500/5 text-[10px] text-slate-400 font-mono leading-relaxed">
                    <p className="font-bold text-slate-300 flex items-center space-x-1">
                      <HelpCircle className="w-3 h-3 text-cyan-455 shrink-0" />
                      <span>RAG Search Framework</span>
                    </p>
                    <p className="mt-1 text-slate-450 text-[9px] leading-tight">
                      Simulating real-time local cosine similarity sweeps inside ChromaDB docker container using nomic-embed model.
                    </p>
                  </div>
                  
                  {filteredChroma.map(doc => (
                    <div
                      key={doc.id}
                      className="p-2.5 border border-white/5 bg-slate-900/10 rounded-sm text-[10px] font-mono leading-relaxed group hover:border-cyan-500/20 transition-all"
                    >
                      <div className="flex items-center justify-between text-[8px] text-slate-550 mb-1">
                        <span className="truncate max-w-[130px]">{doc.metadata.source}</span>
                        <span className="text-cyan-400 bg-cyan-500/10 px-1 py-0.2 rounded-sm font-bold shrink-0">
                          {doc.distance ? `dist: ${doc.distance.toFixed(2)}` : 'embed'}
                        </span>
                      </div>
                      <p className="text-slate-400 line-clamp-3 overflow-hidden text-ellipsis mb-1">{doc.text}.</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Split View Right Viewer Board */}
            <div id="explorer-viewer" className="flex-1 bg-slate-950/10 p-6 overflow-y-auto">
              {activeTab === 'obsidian' && selectedNote ? (
                <div className="space-y-4 max-w-2xl font-mono text-xs">
                  {/* Note Meta Details */}
                  <div className="border-b border-white/5 pb-4">
                    <h2 className="text-base font-bold text-slate-100 tracking-tight leading-snug">{selectedNote.title}</h2>
                    <div className="flex flex-wrap items-center gap-3 mt-2 text-[10px] text-slate-500">
                      <span className="flex items-center space-x-1 bg-slate-900/40 px-2 py-0.5 rounded border border-white/5 text-slate-450">
                        <Clock className="w-3 h-3" />
                        <span>MTime: {new Date(selectedNote.mtime).toLocaleDateString()}</span>
                      </span>
                      <span className="bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 px-2.5 py-0.5 rounded-full font-bold">
                        {selectedNote.folder}
                      </span>
                    </div>
                    {selectedNote.tags.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
                        <Tag className="w-3 h-3 text-slate-600 shrink-0" />
                        {selectedNote.tags.map(tag => (
                          <span key={tag} className="bg-slate-900/40 border border-white/5 text-[9px] text-slate-450 px-2 py-0.5 rounded-sm">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Render note markdown layout with high contrast */}
                  <div className="text-slate-355 leading-relaxed whitespace-pre-wrap py-2 border-l-2 border-cyan-500/25 pl-4 font-sans text-sm">
                    {selectedNote.content}
                  </div>
                </div>
              ) : activeTab === 'obsidian' ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-500 font-mono text-xs">
                  <FileText className="w-8 h-8 text-slate-700 mb-2" />
                  <p>Select or compile an Obsidian study note from the left list.</p>
                </div>
              ) : (
                <div className="space-y-6 max-w-2xl font-mono text-xs">
                  {/* Chroma DB view header */}
                  <div className="border-b border-slate-800 pb-4">
                    <h2 className="text-sm font-bold text-indigo-400 uppercase tracking-wider">ChromaDB Chunk Records Explorer</h2>
                    <p className="text-slate-500 text-[10px] mt-1">
                      Showing chunk indices mapping semantic search similarities directly loaded inside high-performance DB caches.
                    </p>
                    <div className="mt-4 flex items-center space-x-2">
                      <input
                        type="text"
                        value={chromaQuery}
                        onChange={(e) => setChromaQuery(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') fetchChromaResults(chromaQuery); }}
                        placeholder="Search vector database..."
                        className="flex-1 bg-slate-900 border border-slate-800 rounded p-2 text-xs text-slate-100 outline-none focus:border-cyan-500"
                      />
                      <button
                        onClick={() => fetchChromaResults(chromaQuery)}
                        disabled={chromaLoading}
                        className="bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 px-4 py-2 rounded"
                      >
                        {chromaLoading ? 'Searching...' : 'Search'}
                      </button>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {filteredChroma.map(doc => (
                      <div key={doc.id} className="bg-slate-900 border border-slate-800/80 p-4 rounded-md">
                        <div className="flex items-center justify-between border-b border-slate-850 pb-2 mb-2">
                          <span className="text-indigo-300 font-semibold text-[10px] truncate max-w-[340px]">{doc.metadata.source}</span>
                          <span className="bg-slate-950 px-2 py-0.5 rounded text-[9px] text-slate-400 border border-slate-800">
                            ID: {doc.id}
                          </span>
                        </div>
                        <p className="text-slate-300 font-sans leading-relaxed text-xs">{doc.text}</p>
                        <div className="mt-3 flex flex-wrap items-center gap-4 text-[9px] text-slate-500">
                          {doc.metadata.stage && (
                            <span>Stage Stage: <strong className="text-cyan-400">{doc.metadata.stage}</strong></span>
                          )}
                          {doc.metadata.timestamp && (
                            <span>Mapped: {doc.metadata.timestamp}</span>
                          )}
                          {doc.distance && (
                            <span className="text-emerald-400">Similarity Metric: {(1 - doc.distance).toFixed(4)}%</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
