"""
Request logging middleware.

Logs every HTTP request with:
  - method, path, status_code, duration_ms
  - client_ip, request_id (correlation)
  - user_agent (truncated)

Also injects a unique X-Request-ID header into every response.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.access")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with timing and correlation ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.perf_counter()

        response: Response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Attach correlation ID to response
        response.headers["X-Request-ID"] = request_id

        # Log at appropriate level
        status = response.status_code
        log_level = logging.WARNING if status >= 400 else logging.INFO
        if status >= 500:
            log_level = logging.ERROR

        logger.log(
            log_level,
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            status,
            duration_ms,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status,
                "duration_ms": duration_ms,
                "client_ip": _client_ip(request),
                "user_agent": (request.headers.get("user-agent") or "")[:200],
            },
        )
        return response
