import express from "express";
import path from "path";
import fs from "fs";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI } from "@google/genai";
import OpenAI from "openai";
import { createClient } from "redis";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = 3000;
app.use(express.json());

// ─── LLM Providers (3-tier fallback: Nous Portal → Gemini → Ollama) ──────────
const SMC_SYSTEM_INSTRUCTION =
  "You are the Hermes Trading Agent — a precise SMC/ICT specialist for XAUUSD. Demand rigorous risk management in every analysis.";

// Tier 1: Nous Portal (stepfun/step-3.7-flash:free — free tier)
let nousClient: OpenAI | null = null;
const nousModel = process.env.NOUS_MODEL || "stepfun/step-3.7-flash:free";
try {
  if (process.env.NOUS_API_KEY) {
    nousClient = new OpenAI({
      apiKey: process.env.NOUS_API_KEY,
      baseURL: "https://inference-api.nousresearch.com/v1",
    });
    console.log(`[LLM] Nous Portal client initialized (${nousModel})`);
  } else {
    console.log("[LLM] NOUS_API_KEY not set — Nous Portal tier disabled");
  }
} catch (err) {
  console.error("[LLM] Nous Portal init failed:", err);
}

// Tier 2: Gemini (optional)
let ai: GoogleGenAI | null = null;
try {
  if (process.env.GEMINI_API_KEY) {
    ai = new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY,
      httpOptions: { headers: { "User-Agent": "aistudio-build" } }
    });
    console.log("[LLM] Gemini client initialized (gemini-2.5-flash)");
  } else {
    console.log("[LLM] GEMINI_API_KEY not set — Gemini tier disabled");
  }
} catch (err) {
  console.error("[LLM] Gemini init failed:", err);
}

// Tier 3: Ollama (always available if running)
let rawOllama = process.env.OLLAMA_URL || process.env.OLLAMA_HOST || "http://127.0.0.1:11434";
if (!rawOllama.startsWith("http")) {
  rawOllama = `http://${rawOllama === "0.0.0.0" ? "127.0.0.1" : rawOllama}:11434`;
}
const ollamaBaseUrl = rawOllama;
const ollamaModel = process.env.MODEL_ANALYSIS || "hermes3:latest";
let ollamaClient: OpenAI | null = null;
try {
  ollamaClient = new OpenAI({
    apiKey: "ollama",
    baseURL: `${ollamaBaseUrl}/v1`,
  });
  console.log(`[LLM] Ollama client initialized (${ollamaModel} @ ${ollamaBaseUrl})`);
} catch (err) {
  console.error("[LLM] Ollama client init failed:", err);
}

// ─── Redis Clients (State & Pub/Sub) ──────────────────────────────────────────
const redisUrl = process.env.REDIS_URL || "redis://localhost:6379";
const redisClient = createClient({ url: redisUrl });
const redisSub = createClient({ url: redisUrl });

redisClient.on('error', err => console.error('[Redis] Client Error', err));
redisSub.on('error', err => console.error('[Redis] Sub Error', err));

async function initRedis() {
  try {
    await redisClient.connect();
    await redisSub.connect();
    // Initialize LLM status if not present
    const existing = await redisClient.get("LLM_ACTIVE_STATUS");
    if (!existing) {
      await redisClient.set("LLM_ACTIVE_STATUS", JSON.stringify({ tier: "none", model: "none" }));
    }
  } catch (err) {
    console.error("[Redis] Connection failed", err);
  }
}
initRedis();

// Helper to broadcast logs to all dashboards
async function broadcastLog(source: string, level: string, text: string) {
  const entry = { id: `log_${Date.now()}`, timestamp: new Date().toISOString(), source, level, text };
  logs.push(entry);
  if (logs.length > 200) logs.shift();
  try {
    if (redisClient.isOpen) {
      await redisClient.publish("SYSTEM_LOGS", JSON.stringify(entry));
    }
  } catch (err) {
    console.error("[Redis] Failed to publish log:", err);
  }
  return entry;
}

// ─── Runtime state (in-memory cache — real data lives in SQLite/Obsidian/ChromaDB) ──
let currentPrice: number | null = null;
let lastMT5DataTimestamp: number | null = null;

// Minimal in-memory buffers — populated by hydration and live events
let trades: any[] = [];
let closedTrades: any[] = [];
let fairValueGaps: any[] = [];
let orderBlocks: any[] = [];
let liquidityPools: any[] = [];
let skills: any[] = [];
let logs: any[] = [
  {
    id: "log_boot_1",
    timestamp: new Date().toISOString(),
    source: "SYSTEM",
    level: "INFO",
    text: "Hermes server started. Hydrating from persistent services..."
  }
];

let autonomousLoops = {
  nightlyMarketScan:  { lastRun: new Date(0).toISOString(), status: "IDLE", outcome: "" },
  skillAutoCreation:  { lastRun: new Date(0).toISOString(), status: "IDLE", outcome: "" },
  paperTradeReview:   { lastRun: new Date(0).toISOString(), status: "IDLE", outcome: "" },
  hypothesisRandD:    { lastRun: new Date(0).toISOString(), status: "IDLE", outcome: "" }
};

// ─── Tick simulator — only runs when MT5 is silent AND price is seeded ────────
setInterval(() => {
  if (currentPrice === null || isNaN(currentPrice)) return;
  const now = Date.now();
  if (lastMT5DataTimestamp && now - lastMT5DataTimestamp < 10000) return;

  const change = (Math.random() - 0.495) * 0.4;
  currentPrice = parseFloat((currentPrice + change).toFixed(2));

  trades = trades.map(t => {
    const pnl = t.direction === "BUY"
      ? (currentPrice! - t.entryPrice) * t.lotSize * 100
      : (t.entryPrice - currentPrice!) * t.lotSize * 100;
    return { ...t, currentPrice, pnl: parseFloat(pnl.toFixed(2)) };
  });

  if (logs.length > 200) logs.shift();
}, 3000);

// ─── Helpers ──────────────────────────────────────────────────────────────────
async function fetchWithTimeout(url: string, options: any = {}, timeoutMs = 3000): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const r = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    return r;
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
}

function scanObsidianVault(dir: string, baseDir = ""): any[] {
  let results: any[] = [];
  try {
    if (!fs.existsSync(dir)) return results;
    for (const file of fs.readdirSync(dir)) {
      const filePath = path.join(dir, file);
      const rel = baseDir ? path.join(baseDir, file) : file;
      const stat = fs.statSync(filePath);
      if (stat.isDirectory()) {
        results = results.concat(scanObsidianVault(filePath, rel));
      } else if (file.endsWith(".md")) {
        const content = fs.readFileSync(filePath, "utf-8");
        results.push({
          path: rel,
          title: file.replace(/\.md$/, ""),
          content,
          folder: baseDir || "root",
          tags: [],
          mtime: stat.mtime.toISOString()
        });
      }
    }
  } catch (_) {}
  return results;
}

function addLog(source: string, level: string, text: string) {
  logs.push({ id: `log_${Date.now()}`, timestamp: new Date().toISOString(), source, level, text });
  if (logs.length > 200) logs.shift();
}

// ─── Hydrate state from persistent services on startup ────────────────────────
async function hydrateState(): Promise<void> {
  console.log("[Hydrate] Loading state from persistent services...");

  // Active trades from paper_trader
  try {
    const r = await fetchWithTimeout("http://paper_trader:5561/positions", {}, 5000);
    if (r.ok) {
      const data = await r.json();
      if (Array.isArray(data)) {
        trades = data.map((p: any) => ({
          id: String(p.id || p.ticket),
          timestamp: new Date((p.open_time || Date.now() / 1000) * 1000).toISOString(),
          instrument: p.instrument || "XAUUSD",
          direction: String(p.direction || "BUY").toUpperCase(),
          type: p.setup_type || "SMC",
          entryPrice: parseFloat(p.entry_price || 0),
          stopLoss: parseFloat(p.sl || 0),
          takeProfit: parseFloat(p.tp || 0),
          lotSize: parseFloat(p.lots || 0.01),
          currentPrice: parseFloat(p.entry_price || 0),
          pnl: 0,
          status: "OPEN",
          stage: p.mode || "paper",
          riskPercent: parseFloat(p.risk_pct || 1.0),
          rrRatio: parseFloat(p.r_ratio || 2.0),
          notes: p.agent_notes || ""
        }));
        console.log(`[Hydrate] ${trades.length} active positions loaded.`);
      }
    }
  } catch (_) { console.log("[Hydrate] paper_trader not ready yet."); }

  // Closed trades from paper_trader history
  try {
    const r = await fetchWithTimeout("http://paper_trader:5561/history?n=50", {}, 5000);
    if (r.ok) {
      const data = await r.json();
      if (Array.isArray(data)) {
        closedTrades = data.map((p: any) => ({
          id: String(p.id || p.ticket),
          timestamp: new Date((p.open_time || Date.now() / 1000) * 1000).toISOString(),
          instrument: p.instrument || "XAUUSD",
          direction: String(p.direction || "BUY").toUpperCase(),
          type: p.setup_type || "SMC",
          entryPrice: parseFloat(p.entry_price || 0),
          exitPrice: parseFloat(p.close_price || 0),
          stopLoss: parseFloat(p.sl || 0),
          takeProfit: parseFloat(p.tp || 0),
          lotSize: parseFloat(p.lots || 0.01),
          currentPrice: parseFloat(p.close_price || 0),
          pnl: parseFloat(p.profit || 0),
          status: "CLOSED",
          stage: p.mode || "paper",
          riskPercent: parseFloat(p.risk_pct || 1.0),
          rrRatio: parseFloat(p.r_ratio || 2.0),
          closedAt: p.close_time ? new Date(p.close_time * 1000).toISOString() : new Date().toISOString(),
          notes: p.close_reason || ""
        }));
        console.log(`[Hydrate] ${closedTrades.length} closed trades loaded.`);
      }
    }
  } catch (_) {}

  addLog("SYSTEM", "INFO", "State hydration complete. Dashboard ready.");
}

// ─── API Routes ───────────────────────────────────────────────────────────────

app.get("/api/status", async (_req, res) => {
  const check = async (url: string) => {
    try { return (await fetchWithTimeout(url, {}, 1500)).ok; } catch { return false; }
  };

  // mt5 check reads the real ea_connected field — not just HTTP 200
  let mt5EaConnected = false;
  try {
    const mt5r = await fetchWithTimeout("http://mt5_bridge:5558/health", {}, 1500);
    if (mt5r.ok) {
      const mt5data = await mt5r.json();
      mt5EaConnected = mt5data.ea_connected === true;
    }
  } catch { mt5EaConnected = false; }

  const [ollama, rpc, chroma] = await Promise.all([
    check("http://host.docker.internal:11434/api/tags"),
    check("http://host.docker.internal:7778/health"),
    check("http://chromadb:8000/api/v1/heartbeat")
  ]);

  const mt5s = mt5EaConnected ? "connected" : "disconnected";
  res.json({
    ollama: ollama ? "connected" : "disconnected",
    hermesRpc: rpc ? "connected" : "disconnected",
    mt5Zmq: { data: mt5s, draw: mt5s, order: mt5s },
    redis: "connected",
    chromaDb: chroma ? "connected" : "disconnected",
    obsidian: fs.existsSync("/data/obsidian") ? "connected" : "disconnected"
  });
});

app.get("/api/market", async (_req, res) => {
  let price = currentPrice;
  let high: number | null = null;
  let low: number | null = null;
  let fvgList = fairValueGaps;
  let obList = orderBlocks;
  let liqList = liquidityPools;

  // Run preprocessor and MT5 bars in PARALLEL to halve endpoint latency
  const [smcResult, barsResult] = await Promise.allSettled([
    fetchWithTimeout("http://preprocessor:5559/smc_analysis?instrument=XAUUSD&tf=M15&n=300", {}, 5000),
    fetchWithTimeout("http://mt5_bridge:5558/latest_bars?instrument=XAUUSD&tf=M15&n=50", {}, 6000)
  ]);
  try {
    if (smcResult.status === "fulfilled" && smcResult.value.ok) {
      const d = await smcResult.value.json();
      if (d.fvg?.length) fvgList = d.fvg;
      if (d.order_blocks?.length) obList = d.order_blocks;
      if (d.liquidity?.length) liqList = d.liquidity;
    }
  } catch (_) {}
  try {
    if (barsResult.status === "fulfilled" && barsResult.value.ok) {
      const bars = await barsResult.value.json();
      if (Array.isArray(bars) && bars.length > 0) {
        price = bars[bars.length - 1].close;
        high = Math.max(...bars.map((b: any) => b.high));
        low = Math.min(...bars.map((b: any) => b.low));
        currentPrice = price;
        lastMT5DataTimestamp = Date.now();
      }
    }
  } catch (_) {}

  // Fallback: read from live_feed.jsonl on disk
  if (price === null) {
    const feedPath = "/data/market_data/live_feed.jsonl";
    if (fs.existsSync(feedPath)) {
      try {
        const lines = fs.readFileSync(feedPath, "utf-8").split("\n").filter(Boolean);
        const bars = lines.map(l => JSON.parse(l)).filter((b: any) => b.instrument?.toUpperCase() === "XAUUSD");
        if (bars.length > 0) {
          const last = bars[bars.length - 1];
          price = last.close || last.price;
          currentPrice = price;
        }
      } catch (_) {}
    }
  }

  res.json({
    currentPrice: price,
    dailyHigh: high ?? 0,
    dailyLow: low ?? 0,
    sessions: {
      asian:   { open: false, range: high && low ? `${(low + 2).toFixed(2)} - ${(low + 12).toFixed(2)}` : "N/A" },
      london:  { open: true,  range: high && low ? `${(low + 5).toFixed(2)} - ${(high - 5).toFixed(2)}` : "N/A" },
      newYork: { open: true,  range: high && low ? `${(low + 10).toFixed(2)} - ${high.toFixed(2)}` : "N/A" }
    },
    fairValueGaps: fvgList,
    orderBlocks: obList,
    liquidityPools: liqList
  });
});

app.get("/api/trades", async (_req, res) => {
  let activeList = trades;
  let closedList = closedTrades;
  let balance = 0;
  let equity = 0;
  let d_dd = 0.0;
  let w_dd = 0.0;

  try {
    const [posRes, statsRes, histRes] = await Promise.all([
      fetchWithTimeout("http://paper_trader:5561/positions", {}, 2000),
      fetchWithTimeout("http://paper_trader:5561/stats", {}, 2000),
      fetchWithTimeout("http://paper_trader:5561/history", {}, 2000)
    ]);

    if (posRes.ok) {
      const livePos = await posRes.json();
      if (Array.isArray(livePos)) {
        activeList = livePos.map((p: any) => ({
          id: String(p.id || p.ticket),
          timestamp: new Date((p.open_time || Date.now() / 1000) * 1000).toISOString(),
          instrument: p.instrument || "XAUUSD",
          direction: String(p.direction || "BUY").toUpperCase(),
          type: p.setup_type || "SMC",
          entryPrice: parseFloat(p.entry_price || 0),
          stopLoss: parseFloat(p.sl || 0),
          takeProfit: parseFloat(p.tp || 0),
          lotSize: parseFloat(p.lots || 0.01),
          currentPrice: parseFloat(p.current_price || currentPrice || 0),
          pnl: parseFloat(p.profit || 0),
          status: "OPEN",
          stage: p.mode || "paper",
          riskPercent: parseFloat(p.risk_pct || 1.0),
          rrRatio: parseFloat(p.r_ratio || 2.0),
          notes: p.agent_notes || ""
        }));
        trades = activeList;
      }
    }

    if (statsRes.ok) {
      const stats = await statsRes.json();
      balance = stats.balance ?? 0;
      equity = stats.equity ?? 0;
      d_dd = stats.max_drawdown_percent ?? 0;
      w_dd = d_dd * 1.5;
    }

    if (histRes.ok) {
      const hist = await histRes.json();
      if (Array.isArray(hist)) {
        closedList = hist.map((p: any) => ({
          id: String(p.id || p.ticket),
          timestamp: new Date((p.open_time || Date.now() / 1000) * 1000).toISOString(),
          instrument: p.instrument || "XAUUSD",
          direction: String(p.direction || "BUY").toUpperCase(),
          type: p.setup_type || "SMC",
          entryPrice: parseFloat(p.entry_price || 0),
          exitPrice: parseFloat(p.close_price || 0),
          stopLoss: parseFloat(p.sl || 0),
          takeProfit: parseFloat(p.tp || 0),
          lotSize: parseFloat(p.lots || 0.01),
          currentPrice: parseFloat(p.close_price || 0),
          pnl: parseFloat(p.profit || 0),
          status: "CLOSED",
          stage: p.mode || "paper",
          riskPercent: parseFloat(p.risk_pct || 1.0),
          rrRatio: parseFloat(p.r_ratio || 2.0),
          closedAt: p.close_time ? new Date(p.close_time * 1000).toISOString() : new Date().toISOString(),
          notes: p.close_reason || ""
        }));
        closedTrades = closedList;
      }
    }
  } catch (_) {}

  res.json({
    active: activeList,
    closed: closedList,
    balance,
    equity,
    dailyDDPercent: parseFloat(d_dd.toFixed(2)),
    weeklyDDPercent: parseFloat(w_dd.toFixed(2))
  });
});

app.post("/api/trades", async (req, res) => {
  const { direction, type, entryPrice, stopLoss, takeProfit, lotSize, stage, riskPercent } = req.body;

  if (parseFloat(riskPercent) > 1.0) {
    return res.status(400).json({ error: "Risk exceeds 1.0% maximum." });
  }

  const signalPayload = {
    signal_id: "sig_" + Math.random().toString(36).substr(2, 5),
    timestamp: Math.floor(Date.now() / 1000),
    instrument: "XAUUSD",
    direction: direction.toLowerCase(),
    entry_price: parseFloat(entryPrice) || currentPrice || 0,
    entry_type: "market",
    sl: parseFloat(stopLoss),
    tp: parseFloat(takeProfit),
    lots: parseFloat(lotSize) || 0.01,
    timeframe: "M15",
    strategy_id: "manual",
    setup_type: type,
    session: "Active",
    mode: stage || "paper",
    r_ratio: parseFloat(((parseFloat(takeProfit) - parseFloat(entryPrice)) /
                         (parseFloat(entryPrice) - parseFloat(stopLoss))).toFixed(2)) || 2.0,
    confidence: "high",
    agent_notes: `Manual ${stage} order from dashboard.`,
    status: "pending"
  };

  try {
    const r = await fetchWithTimeout("http://paper_trader:5561/signal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(signalPayload)
    }, 4000);

    if (r.ok) {
      const result = await r.json();
      const pos = result.data || {};
      const newTrade = {
        id: String(pos.id || pos.ticket || signalPayload.signal_id),
        timestamp: new Date().toISOString(),
        instrument: "XAUUSD",
        direction,
        type,
        entryPrice: signalPayload.entry_price,
        stopLoss: signalPayload.sl,
        takeProfit: signalPayload.tp,
        lotSize: signalPayload.lots,
        currentPrice,
        pnl: 0,
        status: "OPEN",
        stage: stage || "paper",
        riskPercent: parseFloat(riskPercent) || 1.0,
        rrRatio: signalPayload.r_ratio,
        notes: signalPayload.agent_notes
      };
      trades.push(newTrade);
      addLog("MT5_ORDER", "SUCCESS", `Trade opened: ${direction} ${signalPayload.lots} lots at ${signalPayload.entry_price}`);
      return res.json(newTrade);
    }
  } catch (e: any) {
    addLog("MT5_ORDER", "ERROR", `Trade open failed: ${e.message}`);
  }

  res.status(503).json({ error: "Paper trader unavailable. Trade not placed." });
});

app.post("/api/trades/close/:id", async (req, res) => {
  const tradeId = req.params.id;
  try {
    const r = await fetchWithTimeout(`http://paper_trader:5561/close/${tradeId}`, { method: "POST" }, 5000);
    if (r.ok) {
      trades = trades.filter(t => t.id !== tradeId);
      addLog("MT5_ORDER", "INFO", `Position ${tradeId} closed via paper trader.`);
      return res.json(await r.json());
    }
  } catch (e: any) {
    addLog("MT5_ORDER", "ERROR", `Close failed for ${tradeId}: ${e.message}`);
  }
  res.status(503).json({ error: "Paper trader unavailable." });
});

app.get("/api/logs", (_req, res) => res.json(logs));

app.post("/api/logs", async (req, res) => {
  const { source, level, text } = req.body;
  const entry = await broadcastLog(source || "SYSTEM", level || "INFO", text);
  res.json(entry);
});

app.get("/api/logs/stream", (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  const listener = (message: string, channel: string) => {
    if (channel === "SYSTEM_LOGS") {
      res.write(`data: ${message}\n\n`);
    }
  };

  redisSub.subscribe("SYSTEM_LOGS", listener);
  
  // Send connection ack
  res.write(`data: ${JSON.stringify({ event: 'connected', message: 'SSE Log stream established' })}\n\n`);

  req.on("close", () => {
    redisSub.unsubscribe("SYSTEM_LOGS", listener);
  });
});

app.get("/api/llm/status", async (_req, res) => {
  try {
    const data = await redisClient.get("LLM_ACTIVE_STATUS");
    res.json(data ? JSON.parse(data) : { tier: "none", model: "none" });
  } catch (err) {
    res.json({ tier: "none", model: "none" });
  }
});

app.get("/api/vault", (_req, res) => {
  const vaultPath = "/data/obsidian";
  const notes = fs.existsSync(vaultPath) ? scanObsidianVault(vaultPath) : [];
  res.json(notes);
});

app.post("/api/vault", (req, res) => {
  const { title, content, folder, tags } = req.body;
  const fileName = `${title.replace(/\s+/g, "_")}.md`;
  const folderPath = folder || "root";
  const relativePath = folderPath !== "root" ? `${folderPath}/${fileName}` : fileName;
  const vaultPath = "/data/obsidian";
  const fullPath = path.join(vaultPath, relativePath);

  if (fs.existsSync(vaultPath)) {
    try {
      fs.mkdirSync(path.dirname(fullPath), { recursive: true });
      fs.writeFileSync(fullPath, content, "utf-8");
    } catch (e: any) {
      console.error("Vault write error:", e.message);
    }
  }

  const note = { path: relativePath, title, content, folder: folderPath, tags: tags || [], mtime: new Date().toISOString() };
  addLog("OBSIDIAN", "SUCCESS", `Note saved: ${relativePath}`);
  res.json(note);
});

app.get("/api/vault/search", async (req, res) => {
  const q = (req.query.q as string) || "";
  try {
    const r = await fetchWithTimeout(`http://dashboard:8080/api/vault/search?q=${encodeURIComponent(q)}`, {}, 3000);
    if (r.ok) return res.json(await r.json());
  } catch (_) {}
  res.json([]);
});

app.get("/api/skills", (_req, res) => {
  const skillDirs = [
    "/data/obsidian/04_KNOWLEDGE_BASE/skills",
    "/home/user/.hermes/skills/trading"
  ];
  const found: any[] = [];
  for (const dir of skillDirs) {
    if (!fs.existsSync(dir)) continue;
    try {
      for (const file of fs.readdirSync(dir).filter(f => f.endsWith(".py") || f.endsWith(".md"))) {
        const fp = path.join(dir, file);
        const stat = fs.statSync(fp);
        const content = fs.readFileSync(fp, "utf-8");
        found.push({
          name: file,
          description: content.split("\n").find(l => l.startsWith("#") || l.startsWith('"""'))?.replace(/^[#"]+/, "").trim() || file,
          code: content,
          successRate: 0,
          usageCount: 0,
          lastUpdated: stat.mtime.toISOString()
        });
      }
    } catch (_) {}
  }
  res.json(found.length > 0 ? found : skills);
});

app.post("/api/skills", (req, res) => {
  const { name, description, code } = req.body;
  const skill = { name, description, code, successRate: 0, usageCount: 0, lastUpdated: new Date().toISOString() };
  skills.push(skill);

  // Write to vault disk if available
  const skillPath = `/data/obsidian/04_KNOWLEDGE_BASE/skills/${name}`;
  try {
    if (fs.existsSync("/data/obsidian/04_KNOWLEDGE_BASE/skills")) {
      fs.writeFileSync(skillPath, code, "utf-8");
    }
  } catch (_) {}

  addLog("SYSTEM", "SUCCESS", `New skill saved: ${name}`);
  res.json(skill);
});

app.get("/api/loops", (_req, res) => res.json(autonomousLoops));

app.post("/api/loops/trigger/:loop", async (req, res) => {
  const loop = req.params.loop as keyof typeof autonomousLoops;
  if (!autonomousLoops[loop]) return res.status(400).json({ error: "Unknown loop" });
  if (autonomousLoops[loop].status === "RUNNING") return res.status(409).json({ error: "Already running" });

  autonomousLoops[loop].status = "RUNNING";
  autonomousLoops[loop].lastRun = new Date().toISOString();
  addLog("RPC", "INFO", `Loop triggered: ${loop}`);
  res.json(autonomousLoops[loop]);

  // Execute asynchronously
  (async () => {
    let outcome = "";
    try {
      const prompts: Record<string, string> = {
        nightlyMarketScan:
          "Run the analyse_market_structure skill for XAUUSD M15. Retrieve the last 300 bars, identify all FVGs, Order Blocks, BOS and CHoCH. Write the market study to the Obsidian vault under 01_MARKET_STUDIES.",
        skillAutoCreation:
          "Using the generate_strategy skill, identify the weakest-performing pattern in recent market studies and generate a new Python skill file to detect it. Write the skill to 04_KNOWLEDGE_BASE/skills/ in the vault.",
        paperTradeReview:
          "Run the review_paper_trades skill. Query the paper_trader stats and analyse performance. Write a weekly review note to 03_TRADE_JOURNAL/weekly_reviews/ in the vault.",
        hypothesisRandD:
          "Run the run_backtest skill for the next pending hypothesis in the R&D queue. Submit to the backtester service and write results to 05_RND/results/ in the vault."
      };

      // Fetch paper trade stats for review loop
      let statsContext = "";
      if (loop === "paperTradeReview") {
        try {
          const sr = await fetchWithTimeout("http://paper_trader:5561/stats", {}, 4000);
          if (sr.ok) statsContext = `\n\nCurrent paper trading stats:\n${JSON.stringify(await sr.json(), null, 2)}`;
        } catch (_) {}
      }

      const r = await fetchWithTimeout("http://host.docker.internal:7778/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: prompts[loop] + statsContext, task_type: "analysis" })
      }, 180000);

      outcome = r.ok
        ? `Loop ${loop} completed successfully at ${new Date().toISOString()}.`
        : `Loop ${loop} failed: hermes_rpc returned ${r.status}.`;

    } catch (e: any) {
      outcome = `Loop ${loop} error: ${e.message}`;
    } finally {
      autonomousLoops[loop].status = "IDLE";
      autonomousLoops[loop].outcome = outcome;
      addLog("RPC", outcome.includes("error") || outcome.includes("failed") ? "ERROR" : "SUCCESS", outcome);
    }
  })();
});

app.get("/api/strategy/list", async (_req, res) => {
  try {
    const r = await fetchWithTimeout("http://dashboard:8080/api/strategy/list", {}, 3000);
    if (r.ok) return res.json(await r.json());
  } catch (_) {}
  res.json([]);
});

app.get("/api/errors", async (_req, res) => {
  try {
    const r = await fetchWithTimeout("http://dashboard:8080/api/errors", {}, 3000);
    if (r.ok) return res.json(await r.json());
  } catch (_) {}
  res.json([]);
});

// ─── LLM Analysis endpoint (3-tier fallback: Nous Portal → Gemini → Ollama) ──
function buildAnalysisPrompt(prompt: string, type: string): string {
  if (type === "smc-audit") {
    return `You are the Hermes Trading Agent analyzing XAUUSD.
Current price: $${currentPrice}
FVGs: ${JSON.stringify(fairValueGaps)}
Order Blocks: ${JSON.stringify(orderBlocks)}
Liquidity: ${JSON.stringify(liquidityPools)}

Analyse using SMC/ICT: identify setups, structural context, and entry conditions.
Risk constraints: max 1% per trade, staged trust model (hypothesis→backtest→paper→live).
Respond in professional Markdown.`;
  }
  return prompt;
}

async function setLlmStatus(tier: string, model: string) {
  try {
    if (redisClient.isOpen) {
      await redisClient.set("LLM_ACTIVE_STATUS", JSON.stringify({ tier, model }));
    }
  } catch (err) {
    console.error("[Redis] Failed to set LLM status", err);
  }
}


const DASHBOARD_TOOLS: any[] = [
  {
    type: "function",
    function: {
      name: "get_current_price",
      description: "Get the current market price for an instrument.",
      parameters: {
        type: "object",
        properties: {
          instrument: { type: "string", description: "The symbol, e.g. XAUUSD" }
        },
        required: ["instrument"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "get_account_state",
      description: "Get current MT5 account balance and equity.",
      parameters: { type: "object", properties: {} }
    }
  }
];

async function executeDashboardTool(name: string, args: any): Promise<string> {
  try {
    if (name === "get_current_price") {
      const inst = args.instrument || "XAUUSD";
      const r = await fetchWithTimeout(`http://mt5_bridge:5558/latest_bars?instrument=${inst}&tf=M15&n=1`, {}, 5000);
      if (r.ok) {
        const bars = await r.json();
        if (Array.isArray(bars) && bars.length > 0) return JSON.stringify({ price: bars[bars.length - 1].close });
      }
      return JSON.stringify({ error: "Could not fetch price" });
    }
    if (name === "get_account_state") {
      const r = await fetchWithTimeout("http://mt5_bridge:5558/account_state", {}, 5000);
      if (r.ok) {
        const data = await r.json();
        return JSON.stringify(data);
      }
      return JSON.stringify({ error: "Could not fetch account state" });
    }
    return JSON.stringify({ error: `Tool ${name} not implemented` });
  } catch (e: any) {
    return JSON.stringify({ error: e.message });
  }
}


async function tryNousPortal(finalPrompt: string): Promise<{ text: string; provider: string } | null> {
  if (!nousClient) return null;
  const start = Date.now();
  let messages: any[] = [
    { role: "system", content: SMC_SYSTEM_INSTRUCTION },
    { role: "user", content: finalPrompt }
  ];
  try {
    let completion = await nousClient.chat.completions.create({
      model: nousModel,
      messages: messages,
      max_tokens: 4096,
      temperature: 0.7,
      tools: DASHBOARD_TOOLS
    });
    
    let message = completion.choices?.[0]?.message;
    if (message?.tool_calls && message.tool_calls.length > 0) {
      messages.push(message);
      for (const tc of message.tool_calls as any[]) {
        let args = {};
        try { args = JSON.parse(tc.function.arguments); } catch (e) {}
        const result = await executeDashboardTool(tc.function.name, args);
        messages.push({
          role: "tool",
          tool_call_id: tc.id,
          name: tc.function.name,
          content: result
        });
      }
      completion = await nousClient.chat.completions.create({
        model: nousModel,
        messages: messages,
        max_tokens: 4096,
        temperature: 0.7,
        tools: DASHBOARD_TOOLS
      });
      message = completion.choices?.[0]?.message;
    }
    
    const text = message?.content;
    const latency = Date.now() - start;
    if (text) {
      console.log(`[LLM] Nous Portal (${nousModel}) responded successfully`);
      await setLlmStatus("nous", nousModel);
      await broadcastLog("LLM_CASCADE", "SUCCESS", `Tier 1: Nous Portal (${nousModel}) completed in ${latency}ms`);
      return { text, provider: "nous-portal" };
    }
    return null;
  } catch (e: any) {
    const latency = Date.now() - start;
    console.warn(`[LLM] Nous Portal failed, falling through: ${e.message}`);
    await broadcastLog("LLM_CASCADE", "WARNING", `Tier 1: Nous Portal failed in ${latency}ms - ${e.message}`);
    return null;
  }
}

async function tryGemini(finalPrompt: string): Promise<{ text: string; provider: string } | null> {
  if (!ai) return null;
  const start = Date.now();
  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: finalPrompt,
      config: { systemInstruction: SMC_SYSTEM_INSTRUCTION }
    });
    const text = response.text;
    const latency = Date.now() - start;
    if (text) {
      console.log("[LLM] Gemini (gemini-2.5-flash) responded successfully");
      await setLlmStatus("gemini", "gemini-2.5-flash");
      await broadcastLog("LLM_CASCADE", "SUCCESS", `Tier 2: Gemini (gemini-2.5-flash) completed in ${latency}ms`);
      return { text, provider: "gemini" };
    }
    return null;
  } catch (e: any) {
    const latency = Date.now() - start;
    console.warn("[LLM] Gemini failed, falling through:", e.message);
    await broadcastLog("LLM_CASCADE", "WARNING", `Tier 2: Gemini failed in ${latency}ms - ${e.message}`);
    return null;
  }
}

async function tryOllama(finalPrompt: string): Promise<{ text: string; provider: string } | null> {
  if (!ollamaClient) return null;
  const start = Date.now();
  try {
    const completion = await ollamaClient.chat.completions.create({
      model: ollamaModel,
      messages: [
        { role: "system", content: SMC_SYSTEM_INSTRUCTION },
        { role: "user", content: finalPrompt }
      ],
    });
    const text = completion.choices?.[0]?.message?.content;
    const latency = Date.now() - start;
    if (text) {
      console.log(`[LLM] Ollama (${ollamaModel}) responded successfully`);
      await setLlmStatus("ollama", ollamaModel);
      await broadcastLog("LLM_CASCADE", "SUCCESS", `Tier 3: Ollama (${ollamaModel}) completed in ${latency}ms`);
      return { text, provider: "ollama" };
    }
    return null;
  } catch (e: any) {
    const latency = Date.now() - start;
    console.warn("[LLM] Ollama failed:", e.message);
    await broadcastLog("LLM_CASCADE", "ERROR", `Tier 3: Ollama failed in ${latency}ms - ${e.message}`);
    return null;
  }
}

const analysisHandler = async (req: express.Request, res: express.Response) => {
  const { prompt, type } = req.body;
  const finalPrompt = buildAnalysisPrompt(prompt || "", type || "user-chat");

  // Tier 1: Nous Portal
  const nousResult = await tryNousPortal(finalPrompt);
  if (nousResult) return res.json(nousResult);

  // Tier 2: Gemini
  const geminiResult = await tryGemini(finalPrompt);
  if (geminiResult) return res.json(geminiResult);

  // Tier 3: Ollama
  const ollamaResult = await tryOllama(finalPrompt);
  if (ollamaResult) return res.json(ollamaResult);

  // All tiers failed
  await setLlmStatus("none", "all_failed");
  await broadcastLog("LLM_CASCADE", "ERROR", "All LLM providers unavailable.");
  res.status(503).json({
    error: "All LLM providers unavailable. Configure NOUS_API_KEY, GEMINI_API_KEY, or ensure Ollama is running.",
    provider: "none"
  });
};

// Primary route
app.post("/api/analyze", analysisHandler);
// Backward-compatible alias
app.post("/api/gemini/analyze", analysisHandler);

// ─── Server bootstrap ─────────────────────────────────────────────────────────
async function startServer() {
  // Seed price from MT5 before opening to traffic
  try {
    const r = await fetchWithTimeout("http://mt5_bridge:5558/latest_bars?instrument=XAUUSD&tf=M15&n=1", {}, 5000);
    if (r.ok) {
      const bars = await r.json();
      if (Array.isArray(bars) && bars.length > 0) {
        currentPrice = bars[bars.length - 1].close;
        console.log(`[Startup] Price seeded from MT5: ${currentPrice}`);
      }
    }
  } catch (_) {
    console.log("[Startup] MT5 not ready — price will be seeded on first poll.");
  }

  // Hydrate dashboard state from persistent services
  await hydrateState();

  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({ server: { middlewareMode: true }, appType: "spa" });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (_req: any, res: any) => res.sendFile(path.join(distPath, "index.html")));
  }

  app.listen(PORT, "0.0.0.0", () => console.log(`Hermes React server running on port ${PORT}`));
}

startServer();
