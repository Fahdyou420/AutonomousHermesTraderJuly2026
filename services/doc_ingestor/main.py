import os
import sys
import time
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import redis
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

try:
    import fitz
except ImportError:
    fitz = None

from services.shared.logger import get_logger
from services.shared.error_bus import publish_error

logger = get_logger("doc_ingestor")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
INBOX_DIR = Path("/data/documents/inbox")
PROCESSED_DIR = Path("/data/documents/processed")
FAILED_DIR = Path("/data/documents/failed")
QUEUE_NAME = "doc_chunks_queue"

INBOX_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
FAILED_DIR.mkdir(parents=True, exist_ok=True)


def split_text_into_chunks(text: str, chunk_size_tokens: int = 512, overlap_tokens: int = 64) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunk_size = int(chunk_size_tokens * 0.75) or 384
    overlap = int(overlap_tokens * 0.75) or 48
    if overlap >= chunk_size:
        overlap = chunk_size - 1
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        if i + chunk_size >= len(words):
            break
        i += (chunk_size - overlap)
    return chunks


def detect_instrument(filename: str, peek_text: str) -> str:
    combined = f"{filename} {peek_text[:200]}".lower()
    if "gold" in combined or "xauusd" in combined or "xau" in combined:
        return "XAUUSD"
    elif "eurusd" in combined or "eur" in combined:
        return "EURUSD"
    elif "gbp" in combined or "gbpusd" in combined or "cable" in combined:
        return "GBPUSD"
    elif "jpy" in combined or "usdjpy" in combined:
        return "USDJPY"
    return "GLOBAL"


def move_file(src: Path, dest_dir: Path) -> None:
    dest = dest_dir / src.name
    try:
        if dest.exists():
            dest.unlink()
        shutil.move(str(src), str(dest))
    except Exception as e:
        logger.error(f"Failed to move {src.name} to {dest_dir.name}: {e}")


class DocumentHandler(FileSystemEventHandler):
    def __init__(self, r_client: redis.Redis):
        self.redis = r_client

    def on_created(self, event):
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if file_path.name.startswith(".") or file_path.name.startswith("~"):
            return
        logger.info(f"New document detected: {file_path.name}")
        time.sleep(1.0)  # let write complete
        self.process_file(file_path)

    def process_file(self, file_path: Path):
        ext = file_path.suffix.lower()
        if ext not in [".pdf", ".txt", ".md"]:
            logger.warning(f"Unsupported file type, skipping: {file_path.name}")
            return

        logger.info(f"Processing: {file_path.name}")
        text = ""

        try:
            if ext == ".pdf":
                if fitz is None:
                    raise ImportError("PyMuPDF not installed")
                doc = fitz.open(file_path)
                text = "\n".join([page.get_text() for page in doc])
                doc.close()
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

            text = text.strip()
            if not text:
                logger.warning(f"Empty content in {file_path.name}, skipping.")
                move_file(file_path, PROCESSED_DIR)
                return

            instrument_hint = detect_instrument(file_path.name, text[:200])
            chunks = split_text_into_chunks(text)
            total_chunks = len(chunks)
            date_str = datetime.utcnow().isoformat() + "Z"

            pushed_count = 0
            failed = False

            for i, chunk_text in enumerate(chunks):
                chunk_payload = {
                    "text": chunk_text,
                    "source_file": file_path.name,
                    "chunk_index": i,
                    "total_chunks": total_chunks,
                    "doc_type": ext[1:],
                    "instrument_hint": instrument_hint,
                    "date_ingested": date_str
                }
                try:
                    self.redis.rpush(QUEUE_NAME, json.dumps(chunk_payload))
                    pushed_count += 1
                except Exception as e:
                    logger.error(f"Redis push failed at chunk {i}/{total_chunks} for {file_path.name}: {e}")
                    publish_error("doc_ingestor", "ERROR",
                                  f"Chunk push failed for {file_path.name}",
                                  f"chunk {i}/{total_chunks}: {e}")
                    failed = True
                    break

            if failed:
                logger.error(
                    f"Ingestion incomplete for {file_path.name}: "
                    f"{pushed_count}/{total_chunks} chunks pushed. "
                    f"Moving to /failed for manual retry."
                )
                move_file(file_path, FAILED_DIR)
                return

            logger.info(f"All {pushed_count} chunks pushed for {file_path.name}. Moving to processed.")
            move_file(file_path, PROCESSED_DIR)

        except Exception as e:
            logger.error(f"Unhandled error processing {file_path.name}: {e}", exc_info=True)
            publish_error("doc_ingestor", "ERROR", f"Failed to process {file_path.name}", str(e))
            move_file(file_path, FAILED_DIR)


def main():
    logger.info("Starting Hermes Document Ingestor...")
    r_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        r_client.ping()
        logger.info("Redis connected.")
    except Exception as e:
        logger.critical(f"Redis connection failed: {e}")
        sys.exit(1)

    handler = DocumentHandler(r_client)

    # Process existing inbox files first
    for existing_file in INBOX_DIR.glob("*"):
        if existing_file.is_file() and not existing_file.name.startswith("."):
            handler.process_file(existing_file)

    observer = Observer()
    observer.schedule(handler, path=str(INBOX_DIR), recursive=False)
    observer.start()
    logger.info(f"Watching inbox: {INBOX_DIR}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
