import os
from pathlib import Path
import redis as redis_lib

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
KILL_SWITCH_FILE = Path("/data/trades/kill_switch.active")
REDIS_KEY = "hermes:kill_switch"

def is_kill_switch_active() -> bool:
    """Checks if the emergency kill switch is active (via local file or Redis)."""
    # 1. Check local file (fail-safe/independent of Redis)
    try:
        if KILL_SWITCH_FILE.exists():
            return True
    except Exception:
        pass
    
    # 2. Check Redis
    try:
        r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        active = r.get(REDIS_KEY) == "true"
        r.close()
        return active
    except Exception:
        pass
    
    return False

def activate_kill_switch() -> None:
    """Activates the kill switch (creates local file and sets Redis key)."""
    # Create file
    try:
        KILL_SWITCH_FILE.parent.mkdir(parents=True, exist_ok=True)
        KILL_SWITCH_FILE.touch()
    except Exception:
        pass
    
    # Set Redis key
    try:
        r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
        r.set(REDIS_KEY, "true")
        r.close()
    except Exception:
        pass

def deactivate_kill_switch() -> None:
    """Deactivates the kill switch (removes file and clears Redis key)."""
    # Delete file
    try:
        if KILL_SWITCH_FILE.exists():
            KILL_SWITCH_FILE.unlink()
    except Exception:
        pass
    
    # Delete Redis key
    try:
        r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
        r.delete(REDIS_KEY)
        r.close()
    except Exception:
        pass
