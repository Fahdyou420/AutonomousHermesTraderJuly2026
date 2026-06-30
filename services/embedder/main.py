import os
import sys
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import requests
import redis.asyncio as redis
import chromadb
import schedule
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.shared.logger import get_logger

logger = get_logger("embedder")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
QUEUE_NAME = "doc_chunks_queue"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")

# Parse host/port once at module level — but do NOT connect yet.
_parsed = CHROMA_URL.replace("http://", "").replace("https://", "")
_chroma_host, _chroma_port = (_parsed.split(":", 1) if ":" in _parsed else (_parsed, "8000"))
_chroma_port = int(_chroma_port)

# Global client — set during startup, not at import time.
chroma_client: Optional[chromadb.HttpClient] = None

app = FastAPI(title="Hermes Vector Embedder Service", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


def _connect_chroma() -> bool:
    """Try to create the ChromaDB client. Returns True on success."""
    global chroma_client
    try:
        logger.info(f"Connecting to ChromaDB at {_chroma_host}:{_chroma_port}...")
        chroma_client = chromadb.HttpClient(host=_chroma_host, port=_chroma_port)
        # Immediately test the connection is real by listing collections.
        chroma_client.list_collections()
        logger.info("ChromaDB connection confirmed.")
        return True
    except Exception as e:
        logger.error(f"ChromaDB connection failed: {e}")
        chroma_client = None
        return False


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "chroma_connected": chroma_client is not None,
        "ollama_url": OLLAMA_URL,
        "chroma_url": CHROMA_URL,
    }


@app.get("/stats")
async def get_stats():
    if chroma_client is None:
        return {"status": "error", "message": "ChromaDB not connected"}
    try:
        info = {}
        for name in ["trading_knowledge", "market_memory"]:
            try:
                info[name] = chroma_client.get_collection(name).count()
            except Exception:
                info[name] = 0
        return {"status": "ok", "collections": info}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_embedding(text: str) -> List[float]:
    try:
        r = requests.post(f"{OLLAMA_URL}/api/embeddings",
                          json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
                          timeout=30)
        if r.status_code == 200:
            return r.json().get("embedding", [])
        logger.error(f"Ollama embed failed {r.status_code}: {r.text}")
    except Exception as e:
        logger.error(f"Ollama connection error: {e}")
    return []


async def get_embedding_async(text: str) -> List[float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_embedding, text)


def parse_markdown_frontmatter(content: str) -> Dict[str, str]:
    metadata = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    metadata[k.strip()] = v.strip().replace('"', '').replace("'", "")
    return metadata


def sync_obsidian_notes():
    if chroma_client is None:
        logger.warning("ChromaDB not connected — skipping Obsidian sync.")
        return
    obsidian_path = Path("/data/obsidian")
    if not obsidian_path.exists():
        logger.warning(f"Obsidian path '{obsidian_path}' not found.")
        return
    try:
        collection = chroma_client.get_or_create_collection("market_memory")
    except Exception as e:
        logger.error(f"Cannot create market_memory collection: {e}")
        return

    notes = list(obsidian_path.rglob("*.md"))
    logger.info(f"Syncing {len(notes)} Obsidian notes to ChromaDB...")
    for md_file in notes:
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore").strip()
            if not content:
                continue
            meta = parse_markdown_frontmatter(content)
            mtime = datetime.fromtimestamp(md_file.stat().st_mtime).isoformat() + "Z"
            embedding = get_embedding(content)
            if not embedding:
                continue
            collection.upsert(
                documents=[content],
                embeddings=[embedding],
                metadatas=[{
                    "instrument": str(meta.get("instrument", "GLOBAL")),
                    "timeframe": str(meta.get("timeframe", "GLOBAL")),
                    "date": str(meta.get("date", mtime)),
                    "note_path": str(md_file.relative_to(obsidian_path))
                }],
                ids=[f"obsidian_{md_file.name}_{int(md_file.stat().st_mtime)}"]
            )
        except Exception as e:
            logger.error(f"Note sync failed for {md_file.name}: {e}")


async def process_chunk_payload(payload: Dict[str, Any]):
    if chroma_client is None:
        logger.warning("ChromaDB not connected — dropping chunk.")
        return
    text = payload.get("text", "").strip()
    if not text:
        return
    source = payload.get("source_file", "unknown")
    idx = payload.get("chunk_index", 0)
    embedding = await get_embedding_async(text)
    if not embedding:
        logger.error(f"No embedding for chunk {idx} of {source}")
        return
    try:
        collection = chroma_client.get_or_create_collection("trading_knowledge")
        chunk_id = f"{source}_{idx}"
        collection.upsert(
            documents=[text],
            embeddings=[embedding],
            metadatas=[{
                "source_file": str(source),
                "chunk_index": int(idx),
                "total_chunks": int(payload.get("total_chunks", 1)),
                "doc_type": str(payload.get("doc_type", "txt")),
                "instrument_hint": str(payload.get("instrument_hint", "GLOBAL")),
                "date_ingested": str(payload.get("date_ingested", ""))
            }],
            ids=[chunk_id]
        )
        logger.info(f"Upserted chunk [{chunk_id}] into 'trading_knowledge'.")
    except Exception as e:
        logger.error(f"Chroma upsert failed for chunk {idx}/{source}: {e}")


async def redis_consumer_task():
    logger.info(f"Starting Redis queue watcher for '{QUEUE_NAME}'")
    r_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    while True:
        try:
            res = await r_client.blpop(QUEUE_NAME, timeout=2)
            if res:
                _, json_str = res
                try:
                    await process_chunk_payload(json.loads(json_str))
                except Exception as e:
                    logger.error(f"Chunk JSON parse error: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Redis consumer error: {e}")
            await asyncio.sleep(2)
    await r_client.close()


async def chroma_reconnect_task():
    """Background task that keeps trying to connect to ChromaDB until it succeeds."""
    global chroma_client
    while chroma_client is None:
        logger.info("Retrying ChromaDB connection in 5s...")
        await asyncio.sleep(5)
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, _connect_chroma)
        if success:
            # Once connected, run initial Obsidian sync
            await loop.run_in_executor(None, sync_obsidian_notes)


@app.on_event("startup")
async def startup_services():
    loop = asyncio.get_event_loop()

    # Try connecting immediately — if ChromaDB isn't ready yet, background task retries.
    connected = await loop.run_in_executor(None, _connect_chroma)
    if connected:
        await loop.run_in_executor(None, sync_obsidian_notes)
    else:
        logger.warning("ChromaDB not ready at startup — will retry in background.")
        asyncio.create_task(chroma_reconnect_task())

    asyncio.create_task(redis_consumer_task())

    schedule.every(6).hours.do(lambda: asyncio.get_event_loop().run_in_executor(None, sync_obsidian_notes))
    asyncio.create_task(_schedule_runner())
    logger.info("Embedder startup complete.")


async def _schedule_runner():
    while True:
        schedule.run_pending()
        await asyncio.sleep(5)
