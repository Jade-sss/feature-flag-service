"""
Prometheus metrics for the Feature Flag Service.

Instruments:
  - http_requests_total          — counter by method, path, status
  - http_request_duration_seconds — histogram by method, path
  - http_requests_in_progress    — gauge of active requests
  - flag_evaluations_total       — counter of flag evaluations by result
  - cache_hits_total / cache_misses_total — counter for cache effectiveness

Exposes /metrics endpoint for Prometheus scraping.
"""

import time
import logging

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ── Custom registry (avoids default process/platform collectors in tests) ─────
REGISTRY = CollectorRegistry()

# ── HTTP metrics ──────────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path_template", "status_code"],
    registry=REGISTRY,
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path_template"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=REGISTRY,
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    registry=REGISTRY,
)

# ── Business metrics ──────────────────────────────────────────────────────────

FLAG_EVALUATIONS = Counter(
    "flag_evaluations_total",
    "Total flag evaluations",
    ["result"],  # "true" or "false"
    registry=REGISTRY,
)

CACHE_HITS = Counter(
    "cache_hits_total",
    "Cache hits",
    ["cache_type"],  # "flag" or "eval"
    registry=REGISTRY,
)

CACHE_MISSES = Counter(
    "cache_misses_total",
    "Cache misses",
    ["cache_type"],
    registry=REGISTRY,
)


# ── Helper to normalize paths (collapse IDs into templates) ──────────────────

def _normalize_path(path: str) -> str:
    """Collapse dynamic path segments to avoid high cardinality.

    /flags/my-feature -> /flags/{key}
    /flags/my-feature/overrides/user-42 -> /flags/{key}/overrides/{user_id}
    /api-keys/5 -> /api-keys/{id}
    """
    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "flags":
        if len(parts) == 2 and parts[1] != "evaluate":
            parts[1] = "{key}"
        elif len(parts) >= 3:
            parts[1] = "{key}"
            if len(parts) >= 4 and parts[2] == "overrides":
                if len(parts) == 4:
                    parts[3] = "{user_id}"
    if len(parts) >= 2 and parts[0] == "api-keys":
        if parts[1].isdigit():
            parts[1] = "{id}"
    return "/" + "/".join(parts)


# ── Middleware ────────────────────────────────────────────────────────────────

class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collect HTTP request metrics for Prometheus."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip instrumenting the /metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = _normalize_path(request.url.path)
        REQUESTS_IN_PROGRESS.inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            REQUEST_COUNT.labels(method=method, path_template=path, status_code="500").inc()
            REQUESTS_IN_PROGRESS.dec()
            raise

        duration = time.perf_counter() - start
        status_code = str(response.status_code)

        REQUEST_COUNT.labels(method=method, path_template=path, status_code=status_code).inc()
        REQUEST_DURATION.labels(method=method, path_template=path).observe(duration)
        REQUESTS_IN_PROGRESS.dec()

        return response


# ── Metrics endpoint ─────────────────────────────────────────────────────────

async def metrics_endpoint(request: Request) -> Response:
    """Prometheus scrape target."""
    body = generate_latest(REGISTRY)
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)
