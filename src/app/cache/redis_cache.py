"""
Redis-backed cache for feature flags.

Keys:
  flag:{key}             -> JSON of flag row         (TTL: FLAG_TTL)
  eval:{flag_key}:{uid}  -> "1" or "0"               (TTL: EVAL_TTL)

Invalidation:
  On flag create/update/delete the flag:{key} key and all eval:{key}:* keys
  are removed so the next read hits the DB.

Graceful degradation:
  If Redis is unreachable every cache call returns None / is a no-op so the
  service keeps working (just slower).
"""

import json
import logging
from typing import Optional

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level pool — initialised once via `connect()`, torn down via `close()`.
_pool: Optional[redis.Redis] = None

FLAG_TTL = 300        # 5 min cache for flag data
EVAL_TTL = 60         # 1 min cache for evaluation results


# ── lifecycle ────────────────────────────────────────────────────────────────

async def connect() -> None:
    """Create the shared Redis connection pool."""
    global _pool
    try:
        _pool = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        await _pool.ping()
        logger.info("Redis cache connected (%s)", settings.REDIS_URL)
    except Exception:
        logger.warning("Redis unavailable — caching disabled")
        _pool = None


async def close() -> None:
    """Shut down the Redis pool gracefully."""
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None


def is_available() -> bool:
    return _pool is not None


# ── flag-level cache ─────────────────────────────────────────────────────────

def _flag_key(key: str) -> str:
    return f"flag:{key}"


async def get_flag(key: str) -> Optional[dict]:
    """Return cached flag dict or None."""
    if not _pool:
        return None
    try:
        raw = await _pool.get(_flag_key(key))
        return json.loads(raw) if raw else None
    except Exception:
        logger.debug("cache get_flag error", exc_info=True)
        return None


async def set_flag(key: str, data: dict) -> None:
    """Cache a flag dict."""
    if not _pool:
        return
    try:
        await _pool.set(_flag_key(key), json.dumps(data), ex=FLAG_TTL)
    except Exception:
        logger.debug("cache set_flag error", exc_info=True)


async def invalidate_flag(key: str) -> None:
    """Remove flag data and ALL evaluation results for that flag."""
    if not _pool:
        return
    try:
        pipe = _pool.pipeline()
        pipe.delete(_flag_key(key))
        # scan for eval keys matching this flag
        cursor = "0"
        while cursor:
            cursor, keys = await _pool.scan(
                cursor=cursor, match=f"eval:{key}:*", count=200
            )
            if keys:
                pipe.delete(*keys)
        await pipe.execute()
    except Exception:
        logger.debug("cache invalidate_flag error", exc_info=True)


# ── evaluation-result cache ──────────────────────────────────────────────────

def _eval_key(flag_key: str, user_id: str) -> str:
    return f"eval:{flag_key}:{user_id}"


async def get_evaluation(flag_key: str, user_id: str) -> Optional[bool]:
    """Return cached evaluation bool or None (cache miss)."""
    if not _pool:
        return None
    try:
        raw = await _pool.get(_eval_key(flag_key, user_id))
        if raw is None:
            return None
        return raw == "1"
    except Exception:
        logger.debug("cache get_evaluation error", exc_info=True)
        return None


async def set_evaluation(flag_key: str, user_id: str, enabled: bool) -> None:
    """Cache an evaluation result."""
    if not _pool:
        return
    try:
        await _pool.set(
            _eval_key(flag_key, user_id),
            "1" if enabled else "0",
            ex=EVAL_TTL,
        )
    except Exception:
        logger.debug("cache set_evaluation error", exc_info=True)
