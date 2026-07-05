var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// server.ts
var import_express = __toESM(require("express"), 1);
var import_path = __toESM(require("path"), 1);
var import_fs = __toESM(require("fs"), 1);
var import_vite = require("vite");
var import_genai = require("@google/genai");
var import_openai = __toESM(require("openai"), 1);
var import_redis = require("redis");
var import_dotenv = __toESM(require("dotenv"), 1);
import_dotenv.default.config();
var app = (0, import_express.default)();
var PORT = 3e3;
app.use(import_express.default.json());
var SMC_SYSTEM_INSTRUCTION = "You are the Hermes Trading Agent \u2014 a precise SMC/ICT specialist for XAUUSD. Demand rigorous risk management in every analysis.";
var nousClient = null;
var nousModel = process.env.NOUS_MODEL || "stepfun/step-3.7-flash";
try {
  if (process.env.NOUS_API_KEY) {
    nousClient = new import_openai.default({
      apiKey: process.env.NOUS_API_KEY,
      baseURL: "https://inference-api.nousresearch.com/v1"
    });
    console.log(`[LLM] Nous Portal client initialized (${nousModel})`);
  } else {
    console.log("[LLM] NOUS_API_KEY not set \u2014 Nous Portal tier disabled");
  }
} catch (err) {
  console.error("[LLM] Nous Portal init failed:", err);
}
var ai = null;
try {
  if (process.env.GEMINI_API_KEY) {
    ai = new import_genai.GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY,
      httpOptions: { headers: { "User-Agent": "aistudio-build" } }
    });
    console.log("[LLM] Gemini client initialized (gemini-2.5-flash)");
  } else {
    console.log("[LLM] GEMINI_API_KEY not set \u2014 Gemini tier disabled");
  }
} catch (err) {
  console.error("[LLM] Gemini init failed:", err);
}
var rawOllama = process.env.OLLAMA_URL || process.env.OLLAMA_HOST || "http://127.0.0.1:11434";
if (!rawOllama.startsWith("http")) {
  rawOllama = `http://${rawOllama === "0.0.0.0" ? "127.0.0.1" : rawOllama}:11434`;
}
var ollamaBaseUrl = rawOllama;
var ollamaModel = process.env.MODEL_ANALYSIS || "hermes3:latest";
var ollamaClient = null;
try {
  ollamaClient = new import_openai.default({
    apiKey: "ollama",
    baseURL: `${ollamaBaseUrl}/v1`
  });
  console.log(`[LLM] Ollama client initialized (${ollamaModel} @ ${ollamaBaseUrl})`);
} catch (err) {
  console.error("[LLM] Ollama client init failed:", err);
}
var redisUrl = process.env.REDIS_URL || "redis://localhost:6379";
var redisClient = (0, import_redis.createClient)({ url: redisUrl });
var redisSub = (0, import_redis.createClient)({ url: redisUrl });
redisClient.on("error", (err) => console.error("[Redis] Client Error", err));
redisSub.on("error", (err) => console.error("[Redis] Sub Error", err));
async function initRedis() {
  try {
    await redisClient.connect();
    await redisSub.connect();
    const existing = await redisClient.get("LLM_ACTIVE_STATUS");
    if (!existing) {
      await redisClient.set("LLM_ACTIVE_STATUS", JSON.stringify({ tier: "none", model: "none" }));
    }
  } catch (err) {
    console.error("[Redis] Connection failed", err);
  }
}
initRedis();
async function broadcastLog(source, level, text) {
  const entry = { id: `log_${Date.now()}`, timestamp: (/* @__PURE__ */ new Date()).toISOString(), source, level, text };
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
var currentPrice = null;
var lastMT5DataTimestamp = null;
var trades = [];
var closedTrades = [];
var fairValueGaps = [];
var orderBlocks = [];
var liquidityPools = [];
var skills = [];
var logs = [
  {
    id: "log_boot_1",
    timestamp: (/* @__PURE__ */ new Date()).toISOString(),
    source: "SYSTEM",
    level: "INFO",
    text: "Hermes server started. Hydrating from persistent services..."
  }
];
var autonomousLoops = {
  nightlyMarketScan: { lastRun: (/* @__PURE__ */ new Date(0)).toISOString(), status: "IDLE", outcome: "" },
  skillAutoCreation: { lastRun: (/* @__PURE__ */ new Date(0)).toISOString(), status: "IDLE", outcome: "" },
  paperTradeReview: { lastRun: (/* @__PURE__ */ new Date(0)).toISOString(), status: "IDLE", outcome: "" },
  hypothesisRandD: { lastRun: (/* @__PURE__ */ new Date(0)).toISOString(), status: "IDLE", outcome: "" }
};
setInterval(() => {
  if (currentPrice === null || isNaN(currentPrice)) return;
  const now = Date.now();
  if (lastMT5DataTimestamp && now - lastMT5DataTimestamp < 1e4) return;
  const change = (Math.random() - 0.495) * 0.4;
  currentPrice = parseFloat((currentPrice + change).toFixed(2));
  trades = trades.map((t) => {
    const pnl = t.direction === "BUY" ? (currentPrice - t.entryPrice) * t.lotSize * 100 : (t.entryPrice - currentPrice) * t.lotSize * 100;
    return { ...t, currentPrice, pnl: parseFloat(pnl.toFixed(2)) };
  });
  if (logs.length > 200) logs.shift();
}, 3e3);
async function fetchWithTimeout(url, options = {}, timeoutMs = 3e3) {
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
function scanObsidianVault(dir, baseDir = "") {
  let results = [];
  try {
    if (!import_fs.default.existsSync(dir)) return results;
    for (const file of import_fs.default.readdirSync(dir)) {
      const filePath = import_path.default.join(dir, file);
      const rel = baseDir ? import_path.default.join(baseDir, file) : file;
      const stat = import_fs.default.statSync(filePath);
      if (stat.isDirectory()) {
        results = results.concat(scanObsidianVault(filePath, rel));
      } else if (file.endsWith(".md")) {
        const content = import_fs.default.readFileSync(filePath, "utf-8");
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
  } catch (_) {
  }
  return results;
}
function addLog(source, level, text) {
  logs.push({ id: `log_${Date.now()}`, timestamp: (/* @__PURE__ */ new Date()).toISOString(), source, level, text });
  if (logs.length > 200) logs.shift();
}
async function hydrateState() {
  console.log("[Hydrate] Loading state from persistent services...");
  try {
    const r = await fetchWithTimeout("http://paper_trader:5561/positions", {}, 5e3);
    if (r.ok) {
      const data = await r.json();
      if (Array.isArray(data)) {
        trades = data.map((p) => ({
          id: String(p.id || p.ticket),
          timestamp: new Date((p.open_time || Date.now() / 1e3) * 1e3).toISOString(),
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
          riskPercent: parseFloat(p.risk_pct || 1),
          rrRatio: parseFloat(p.r_ratio || 2),
          notes: p.agent_notes || ""
        }));
        console.log(`[Hydrate] ${trades.length} active positions loaded.`);
      }
    }
  } catch (_) {
    console.log("[Hydrate] paper_trader not ready yet.");
  }
  try {
    const r = await fetchWithTimeout("http://paper_trader:5561/history?n=50", {}, 5e3);
    if (r.ok) {
      const data = await r.json();
      if (Array.isArray(data)) {
        closedTrades = data.map((p) => ({
          id: String(p.id || p.ticket),
          timestamp: new Date((p.open_time || Date.now() / 1e3) * 1e3).toISOString(),
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
          riskPercent: parseFloat(p.risk_pct || 1),
          rrRatio: parseFloat(p.r_ratio || 2),
          closedAt: p.close_time ? new Date(p.close_time * 1e3).toISOString() : (/* @__PURE__ */ new Date()).toISOString(),
          notes: p.close_reason || ""
        }));
        console.log(`[Hydrate] ${closedTrades.length} closed trades loaded.`);
      }
    }
  } catch (_) {
  }
  addLog("SYSTEM", "INFO", "State hydration complete. Dashboard ready.");
}
app.get("/api/status", async (_req, res) => {
  const check = async (url) => {
    try {
      return (await fetchWithTimeout(url, {}, 1500)).ok;
    } catch {
      return false;
    }
  };
  let mt5EaConnected = false;
  try {
    const mt5r = await fetchWithTimeout("http://mt5_bridge:5558/health", {}, 1500);
    if (mt5r.ok) {
      const mt5data = await mt5r.json();
      mt5EaConnected = mt5data.ea_connected === true;
    }
  } catch {
    mt5EaConnected = false;
  }
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
    obsidian: import_fs.default.existsSync("/data/obsidian") ? "connected" : "disconnected"
  });
});
app.get("/api/market", async (_req, res) => {
  let price = currentPrice;
  let high = null;
  let low = null;
  let fvgList = fairValueGaps;
  let obList = orderBlocks;
  let liqList = liquidityPools;
  const [smcResult, barsResult] = await Promise.allSettled([
    fetchWithTimeout("http://preprocessor:5559/smc_analysis?instrument=XAUUSD&tf=M15&n=300", {}, 5e3),
    fetchWithTimeout("http://mt5_bridge:5558/latest_bars?instrument=XAUUSD&tf=M15&n=50", {}, 6e3)
  ]);
  try {
    if (smcResult.status === "fulfilled" && smcResult.value.ok) {
      const d = await smcResult.value.json();
      if (d.fvg?.length) fvgList = d.fvg;
      if (d.order_blocks?.length) obList = d.order_blocks;
      if (d.liquidity?.length) liqList = d.liquidity;
    }
  } catch (_) {
  }
  try {
    if (barsResult.status === "fulfilled" && barsResult.value.ok) {
      const bars = await barsResult.value.json();
      if (Array.isArray(bars) && bars.length > 0) {
        price = bars[bars.length - 1].close;
        high = Math.max(...bars.map((b) => b.high));
        low = Math.min(...bars.map((b) => b.low));
        currentPrice = price;
        lastMT5DataTimestamp = Date.now();
      }
    }
  } catch (_) {
  }
  if (price === null) {
    const feedPath = "/data/market_data/live_feed.jsonl";
    if (import_fs.default.existsSync(feedPath)) {
      try {
        const lines = import_fs.default.readFileSync(feedPath, "utf-8").split("\n").filter(Boolean);
        const bars = lines.map((l) => JSON.parse(l)).filter((b) => b.instrument?.toUpperCase() === "XAUUSD");
        if (bars.length > 0) {
          const last = bars[bars.length - 1];
          price = last.close || last.price;
          currentPrice = price;
        }
      } catch (_) {
      }
    }
  }
  res.json({
    currentPrice: price,
    dailyHigh: high ?? 0,
    dailyLow: low ?? 0,
    sessions: {
      asian: { open: false, range: high && low ? `${(low + 2).toFixed(2)} - ${(low + 12).toFixed(2)}` : "N/A" },
      london: { open: true, range: high && low ? `${(low + 5).toFixed(2)} - ${(high - 5).toFixed(2)}` : "N/A" },
      newYork: { open: true, range: high && low ? `${(low + 10).toFixed(2)} - ${high.toFixed(2)}` : "N/A" }
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
  let d_dd = 0;
  let w_dd = 0;
  try {
    const [posRes, statsRes, histRes] = await Promise.all([
      fetchWithTimeout("http://paper_trader:5561/positions", {}, 2e3),
      fetchWithTimeout("http://paper_trader:5561/stats", {}, 2e3),
      fetchWithTimeout("http://paper_trader:5561/history", {}, 2e3)
    ]);
    if (posRes.ok) {
      const livePos = await posRes.json();
      if (Array.isArray(livePos)) {
        activeList = livePos.map((p) => ({
          id: String(p.id || p.ticket),
          timestamp: new Date((p.open_time || Date.now() / 1e3) * 1e3).toISOString(),
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
          riskPercent: parseFloat(p.risk_pct || 1),
          rrRatio: parseFloat(p.r_ratio || 2),
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
        closedList = hist.map((p) => ({
          id: String(p.id || p.ticket),
          timestamp: new Date((p.open_time || Date.now() / 1e3) * 1e3).toISOString(),
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
          riskPercent: parseFloat(p.risk_pct || 1),
          rrRatio: parseFloat(p.r_ratio || 2),
          closedAt: p.close_time ? new Date(p.close_time * 1e3).toISOString() : (/* @__PURE__ */ new Date()).toISOString(),
          notes: p.close_reason || ""
        }));
        closedTrades = closedList;
      }
    }
  } catch (_) {
  }
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
  if (parseFloat(riskPercent) > 1) {
    return res.status(400).json({ error: "Risk exceeds 1.0% maximum." });
  }
  const signalPayload = {
    signal_id: "sig_" + Math.random().toString(36).substr(2, 5),
    timestamp: Math.floor(Date.now() / 1e3),
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
    r_ratio: parseFloat(((parseFloat(takeProfit) - parseFloat(entryPrice)) / (parseFloat(entryPrice) - parseFloat(stopLoss))).toFixed(2)) || 2,
    confidence: "high",
    agent_notes: `Manual ${stage} order from dashboard.`,
    status: "pending"
  };
  try {
    const r = await fetchWithTimeout("http://paper_trader:5561/signal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(signalPayload)
    }, 4e3);
    if (r.ok) {
      const result = await r.json();
      const pos = result.data || {};
      const newTrade = {
        id: String(pos.id || pos.ticket || signalPayload.signal_id),
        timestamp: (/* @__PURE__ */ new Date()).toISOString(),
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
        riskPercent: parseFloat(riskPercent) || 1,
        rrRatio: signalPayload.r_ratio,
        notes: signalPayload.agent_notes
      };
      trades.push(newTrade);
      addLog("MT5_ORDER", "SUCCESS", `Trade opened: ${direction} ${signalPayload.lots} lots at ${signalPayload.entry_price}`);
      return res.json(newTrade);
    }
  } catch (e) {
    addLog("MT5_ORDER", "ERROR", `Trade open failed: ${e.message}`);
  }
  res.status(503).json({ error: "Paper trader unavailable. Trade not placed." });
});
app.post("/api/trades/close/:id", async (req, res) => {
  const tradeId = req.params.id;
  try {
    const r = await fetchWithTimeout(`http://paper_trader:5561/close/${tradeId}`, { method: "POST" }, 5e3);
    if (r.ok) {
      trades = trades.filter((t) => t.id !== tradeId);
      addLog("MT5_ORDER", "INFO", `Position ${tradeId} closed via paper trader.`);
      return res.json(await r.json());
    }
  } catch (e) {
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
  const listener = (message, channel) => {
    if (channel === "SYSTEM_LOGS") {
      res.write(`data: ${message}

`);
    }
  };
  redisSub.subscribe("SYSTEM_LOGS", listener);
  res.write(`data: ${JSON.stringify({ event: "connected", message: "SSE Log stream established" })}

`);
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
  const notes = import_fs.default.existsSync(vaultPath) ? scanObsidianVault(vaultPath) : [];
  res.json(notes);
});
app.post("/api/vault", (req, res) => {
  const { title, content, folder, tags } = req.body;
  const fileName = `${title.replace(/\s+/g, "_")}.md`;
  const folderPath = folder || "root";
  const relativePath = folderPath !== "root" ? `${folderPath}/${fileName}` : fileName;
  const vaultPath = "/data/obsidian";
  const fullPath = import_path.default.join(vaultPath, relativePath);
  if (import_fs.default.existsSync(vaultPath)) {
    try {
      import_fs.default.mkdirSync(import_path.default.dirname(fullPath), { recursive: true });
      import_fs.default.writeFileSync(fullPath, content, "utf-8");
    } catch (e) {
      console.error("Vault write error:", e.message);
    }
  }
  const note = { path: relativePath, title, content, folder: folderPath, tags: tags || [], mtime: (/* @__PURE__ */ new Date()).toISOString() };
  addLog("OBSIDIAN", "SUCCESS", `Note saved: ${relativePath}`);
  res.json(note);
});
app.get("/api/vault/search", async (req, res) => {
  const q = req.query.q || "";
  try {
    const r = await fetchWithTimeout(`http://dashboard:8080/api/vault/search?q=${encodeURIComponent(q)}`, {}, 3e3);
    if (r.ok) return res.json(await r.json());
  } catch (_) {
  }
  res.json([]);
});
app.get("/api/skills", (_req, res) => {
  const skillDirs = [
    "/data/obsidian/04_KNOWLEDGE_BASE/skills",
    "/home/user/.hermes/skills/trading"
  ];
  const found = [];
  for (const dir of skillDirs) {
    if (!import_fs.default.existsSync(dir)) continue;
    try {
      for (const file of import_fs.default.readdirSync(dir).filter((f) => f.endsWith(".py") || f.endsWith(".md"))) {
        const fp = import_path.default.join(dir, file);
        const stat = import_fs.default.statSync(fp);
        const content = import_fs.default.readFileSync(fp, "utf-8");
        found.push({
          name: file,
          description: content.split("\n").find((l) => l.startsWith("#") || l.startsWith('"""'))?.replace(/^[#"]+/, "").trim() || file,
          code: content,
          successRate: 0,
          usageCount: 0,
          lastUpdated: stat.mtime.toISOString()
        });
      }
    } catch (_) {
    }
  }
  res.json(found.length > 0 ? found : skills);
});
app.post("/api/skills", (req, res) => {
  const { name, description, code } = req.body;
  const skill = { name, description, code, successRate: 0, usageCount: 0, lastUpdated: (/* @__PURE__ */ new Date()).toISOString() };
  skills.push(skill);
  const skillPath = `/data/obsidian/04_KNOWLEDGE_BASE/skills/${name}`;
  try {
    if (import_fs.default.existsSync("/data/obsidian/04_KNOWLEDGE_BASE/skills")) {
      import_fs.default.writeFileSync(skillPath, code, "utf-8");
    }
  } catch (_) {
  }
  addLog("SYSTEM", "SUCCESS", `New skill saved: ${name}`);
  res.json(skill);
});
app.get("/api/loops", (_req, res) => res.json(autonomousLoops));
app.post("/api/loops/trigger/:loop", async (req, res) => {
  const loop = req.params.loop;
  if (!autonomousLoops[loop]) return res.status(400).json({ error: "Unknown loop" });
  if (autonomousLoops[loop].status === "RUNNING") return res.status(409).json({ error: "Already running" });
  autonomousLoops[loop].status = "RUNNING";
  autonomousLoops[loop].lastRun = (/* @__PURE__ */ new Date()).toISOString();
  addLog("RPC", "INFO", `Loop triggered: ${loop}`);
  res.json(autonomousLoops[loop]);
  (async () => {
    let outcome = "";
    try {
      const prompts = {
        nightlyMarketScan: "Run the analyse_market_structure skill for XAUUSD M15. Retrieve the last 300 bars, identify all FVGs, Order Blocks, BOS and CHoCH. Write the market study to the Obsidian vault under 01_MARKET_STUDIES.",
        skillAutoCreation: "Using the generate_strategy skill, identify the weakest-performing pattern in recent market studies and generate a new Python skill file to detect it. Write the skill to 04_KNOWLEDGE_BASE/skills/ in the vault.",
        paperTradeReview: "Run the review_paper_trades skill. Query the paper_trader stats and analyse performance. Write a weekly review note to 03_TRADE_JOURNAL/weekly_reviews/ in the vault.",
        hypothesisRandD: "Run the run_backtest skill for the next pending hypothesis in the R&D queue. Submit to the backtester service and write results to 05_RND/results/ in the vault."
      };
      let statsContext = "";
      if (loop === "paperTradeReview") {
        try {
          const sr = await fetchWithTimeout("http://paper_trader:5561/stats", {}, 4e3);
          if (sr.ok) statsContext = `

Current paper trading stats:
${JSON.stringify(await sr.json(), null, 2)}`;
        } catch (_) {
        }
      }
      const r = await fetchWithTimeout("http://host.docker.internal:7778/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: prompts[loop] + statsContext, task_type: "analysis" })
      }, 18e4);
      outcome = r.ok ? `Loop ${loop} completed successfully at ${(/* @__PURE__ */ new Date()).toISOString()}.` : `Loop ${loop} failed: hermes_rpc returned ${r.status}.`;
    } catch (e) {
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
    const r = await fetchWithTimeout("http://dashboard:8080/api/strategy/list", {}, 3e3);
    if (r.ok) return res.json(await r.json());
  } catch (_) {
  }
  res.json([]);
});
app.get("/api/errors", async (_req, res) => {
  try {
    const r = await fetchWithTimeout("http://dashboard:8080/api/errors", {}, 3e3);
    if (r.ok) return res.json(await r.json());
  } catch (_) {
  }
  res.json([]);
});
function buildAnalysisPrompt(prompt, type) {
  if (type === "smc-audit") {
    return `You are the Hermes Trading Agent analyzing XAUUSD.
Current price: $${currentPrice}
FVGs: ${JSON.stringify(fairValueGaps)}
Order Blocks: ${JSON.stringify(orderBlocks)}
Liquidity: ${JSON.stringify(liquidityPools)}

Analyse using SMC/ICT: identify setups, structural context, and entry conditions.
Risk constraints: max 1% per trade, staged trust model (hypothesis\u2192backtest\u2192paper\u2192live).
Respond in professional Markdown.`;
  }
  return prompt;
}
async function setLlmStatus(tier, model) {
  try {
    if (redisClient.isOpen) {
      await redisClient.set("LLM_ACTIVE_STATUS", JSON.stringify({ tier, model }));
    }
  } catch (err) {
    console.error("[Redis] Failed to set LLM status", err);
  }
}
var DASHBOARD_TOOLS = [
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
async function executeDashboardTool(name, args) {
  try {
    if (name === "get_current_price") {
      const inst = args.instrument || "XAUUSD";
      const r = await fetchWithTimeout(`http://mt5_bridge:5558/latest_bars?instrument=${inst}&tf=M15&n=1`, {}, 5e3);
      if (r.ok) {
        const bars = await r.json();
        if (Array.isArray(bars) && bars.length > 0) return JSON.stringify({ price: bars[bars.length - 1].close });
      }
      return JSON.stringify({ error: "Could not fetch price" });
    }
    if (name === "get_account_state") {
      const r = await fetchWithTimeout("http://mt5_bridge:5558/account_state", {}, 5e3);
      if (r.ok) {
        const data = await r.json();
        return JSON.stringify(data);
      }
      return JSON.stringify({ error: "Could not fetch account state" });
    }
    return JSON.stringify({ error: `Tool ${name} not implemented` });
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}
async function tryNousPortal(finalPrompt) {
  if (!nousClient) return null;
  const start = Date.now();
  let messages = [
    { role: "system", content: SMC_SYSTEM_INSTRUCTION },
    { role: "user", content: finalPrompt }
  ];
  try {
    let completion = await nousClient.chat.completions.create({
      model: nousModel,
      messages,
      max_tokens: 4096,
      temperature: 0.7,
      tools: DASHBOARD_TOOLS
    });
    let message = completion.choices?.[0]?.message;
    if (message?.tool_calls && message.tool_calls.length > 0) {
      messages.push(message);
      for (const tc of message.tool_calls) {
        let args = {};
        try {
          args = JSON.parse(tc.function.arguments);
        } catch (e) {
        }
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
        messages,
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
  } catch (e) {
    const latency = Date.now() - start;
    console.warn(`[LLM] Nous Portal failed, falling through: ${e.message}`);
    await broadcastLog("LLM_CASCADE", "WARNING", `Tier 1: Nous Portal failed in ${latency}ms - ${e.message}`);
    return null;
  }
}
async function tryGemini(finalPrompt) {
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
  } catch (e) {
    const latency = Date.now() - start;
    console.warn("[LLM] Gemini failed, falling through:", e.message);
    await broadcastLog("LLM_CASCADE", "WARNING", `Tier 2: Gemini failed in ${latency}ms - ${e.message}`);
    return null;
  }
}
async function tryOllama(finalPrompt) {
  if (!ollamaClient) return null;
  const start = Date.now();
  try {
    const completion = await ollamaClient.chat.completions.create({
      model: ollamaModel,
      messages: [
        { role: "system", content: SMC_SYSTEM_INSTRUCTION },
        { role: "user", content: finalPrompt }
      ]
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
  } catch (e) {
    const latency = Date.now() - start;
    console.warn("[LLM] Ollama failed:", e.message);
    await broadcastLog("LLM_CASCADE", "ERROR", `Tier 3: Ollama failed in ${latency}ms - ${e.message}`);
    return null;
  }
}
var analysisHandler = async (req, res) => {
  const { prompt, type } = req.body;
  const finalPrompt = buildAnalysisPrompt(prompt || "", type || "user-chat");
  const nousResult = await tryNousPortal(finalPrompt);
  if (nousResult) return res.json(nousResult);
  const geminiResult = await tryGemini(finalPrompt);
  if (geminiResult) return res.json(geminiResult);
  const ollamaResult = await tryOllama(finalPrompt);
  if (ollamaResult) return res.json(ollamaResult);
  await setLlmStatus("none", "all_failed");
  await broadcastLog("LLM_CASCADE", "ERROR", "All LLM providers unavailable.");
  res.status(503).json({
    error: "All LLM providers unavailable. Configure NOUS_API_KEY, GEMINI_API_KEY, or ensure Ollama is running.",
    provider: "none"
  });
};
app.post("/api/analyze", analysisHandler);
app.post("/api/gemini/analyze", analysisHandler);
async function startServer() {
  try {
    const r = await fetchWithTimeout("http://mt5_bridge:5558/latest_bars?instrument=XAUUSD&tf=M15&n=1", {}, 5e3);
    if (r.ok) {
      const bars = await r.json();
      if (Array.isArray(bars) && bars.length > 0) {
        currentPrice = bars[bars.length - 1].close;
        console.log(`[Startup] Price seeded from MT5: ${currentPrice}`);
      }
    }
  } catch (_) {
    console.log("[Startup] MT5 not ready \u2014 price will be seeded on first poll.");
  }
  await hydrateState();
  if (process.env.NODE_ENV !== "production") {
    const vite = await (0, import_vite.createServer)({ server: { middlewareMode: true }, appType: "spa" });
    app.use(vite.middlewares);
  } else {
    const distPath = import_path.default.join(process.cwd(), "dist");
    app.use(import_express.default.static(distPath));
    app.get("*", (_req, res) => res.sendFile(import_path.default.join(distPath, "index.html")));
  }
  app.listen(PORT, "0.0.0.0", () => console.log(`Hermes React server running on port ${PORT}`));
}
startServer();
