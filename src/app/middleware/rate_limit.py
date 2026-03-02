"""
Sliding-window rate limiter middleware backed by Redis.

Strategy:
  Uses a Redis sorted set per client IP to track request timestamps.
  Falls back to an in-memory dict when Redis is unavailable.

Headers added to every response:
  X-RateLimit-Limit     — max requests allowed in window
  X-RateLimit-Remaining — requests left in current window
  X-RateLimit-Reset     — epoch seconds when window resets

Returns 429 Too Many Requests when the limit is exceeded.
"""

import time
import logging
from collections import defaultdict
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

import redis.asyncio as aioredis

from app.core.config import settings
from app.cache import redis_cache

logger = logging.getLogger(__name__)

# In-memory fallback store: {client_ip: [timestamps]}
_mem_store: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    """Extract client IP, honoring X-Forwarded-For behind a reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP sliding window rate limiter.

    Config (via Settings):
      RATE_LIMIT_REQUESTS — max requests per window (default 100)
      RATE_LIMIT_WINDOW   — window size in seconds (default 60)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health check
        if request.url.path == "/":
            return await call_next(request)

        ip = _client_ip(request)
        limit = settings.RATE_LIMIT_REQUESTS
        window = settings.RATE_LIMIT_WINDOW
        now = time.time()
        window_start = now - window

        remaining: int
        reset_at: float = now + window

        # Try Redis first, fall back to in-memory
        if redis_cache.is_available():
            remaining = await self._check_redis(ip, now, window_start, limit, window)
        else:
            remaining = self._check_memory(ip, now, window_start, limit)

        if remaining < 0:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_at)),
                    "Retry-After": str(window),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        response.headers["X-RateLimit-Reset"] = str(int(reset_at))
        return response

    # ── Redis-backed sliding window ──────────────────────────────────────

    async def _check_redis(
        self, ip: str, now: float, window_start: float, limit: int, window: int
    ) -> int:
        """Returns remaining requests (negative means over-limit)."""
        key = f"ratelimit:{ip}"
        pool = redis_cache._pool
        try:
            pipe = pool.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)  # prune old entries
            pipe.zadd(key, {str(now): now})               # add current request
            pipe.zcard(key)                                # count in window
            pipe.expire(key, window)                       # auto-expire key
            results = await pipe.execute()
            count = results[2]
            return limit - count
        except Exception:
            logger.debug("rate limit redis error, falling back to memory", exc_info=True)
            return self._check_memory(ip, now, window_start, limit)

    # ── In-memory fallback ───────────────────────────────────────────────

    def _check_memory(self, ip: str, now: float, window_start: float, limit: int) -> int:
        timestamps = _mem_store[ip]
        # Prune old entries
        _mem_store[ip] = [t for t in timestamps if t > window_start]
        _mem_store[ip].append(now)
        count = len(_mem_store[ip])
        return limit - count
