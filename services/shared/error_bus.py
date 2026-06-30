"""
Hermes Centralized Error Bus
Publishes structured errors to Redis so any service or dashboard can read them.
"""
import os
import json
import time
import redis as redis_lib

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
ERROR_LOG_KEY = "hermes:errors"
MAX_ERRORS = 500


def publish_error(service: str, level: str, message: str, detail: str = "") -> None:
    """Push a structured error to the shared Redis error bus. Never raises."""
    try:
        r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
        entry = json.dumps({
            "timestamp": int(time.time()),
            "service": service,
            "level": level,      # "ERROR", "CRITICAL", "WARNING"
            "message": message,
            "detail": detail
        })
        r.lpush(ERROR_LOG_KEY, entry)
        r.ltrim(ERROR_LOG_KEY, 0, MAX_ERRORS - 1)
        r.close()
    except Exception:
        pass  # Error reporting must never crash the caller


def get_recent_errors(n: int = 100):
    """Retrieve recent errors from the shared bus."""
    try:
        r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
        raw = r.lrange(ERROR_LOG_KEY, 0, n - 1)
        r.close()
        return [json.loads(e) for e in raw]
    except Exception:
        return []
