from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from starlette.routing import Route

from app.api.routers import flags
from app.api.routers import api_keys
from app.cache import redis_cache
from app.core.logging_config import setup_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.prometheus import PrometheusMiddleware, metrics_endpoint

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    setup_logging()
    await redis_cache.connect()
    logger.info("Feature Flag Service started")
    yield
    # shutdown
    await redis_cache.close()
    logger.info("Feature Flag Service stopped")


app = FastAPI(title="Feature Flag Service", lifespan=lifespan)

# ── Middleware (outermost first) ──────────────────────────────────────────
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(PrometheusMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────
app.include_router(flags.router)
app.include_router(api_keys.router)

# ── Observability endpoints (no auth) ─────────────────────────────────────
app.routes.append(Route("/metrics", metrics_endpoint, methods=["GET"]))


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health_check():
    """Deep health check — verifies DB and Redis connectivity."""
    checks: dict = {"status": "ok", "db": "ok", "cache": "ok"}

    # Check DB
    try:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1" if False else __import__("sqlalchemy").text("SELECT 1"))
    except Exception as exc:
        checks["db"] = f"error: {exc}"
        checks["status"] = "degraded"

    # Check Redis
    if redis_cache.is_available():
        try:
            await redis_cache._pool.ping()
        except Exception as exc:
            checks["cache"] = f"error: {exc}"
            checks["status"] = "degraded"
    else:
        checks["cache"] = "unavailable"
        checks["status"] = "degraded"

    return checks
