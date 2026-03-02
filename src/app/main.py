from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.routing import Route

from app.api.routers import flags
from app.api.routers import api_keys
from app.cache import redis_cache
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.exceptions import register_exception_handlers
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.prometheus import PrometheusMiddleware, metrics_endpoint
from app.middleware.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ───────────────────────────────────────────────────────────
    setup_logging()
    logger.info(
        "Starting Feature Flag Service (env=%s, auth=%s)",
        settings.ENV,
        settings.AUTH_ENABLED,
    )
    await redis_cache.connect()

    # Warn if running in production without critical config
    if settings.ENV == "production":
        if not settings.AUTH_ENABLED:
            logger.warning("AUTH_ENABLED is False in production — this is insecure!")
        if not settings.MASTER_API_KEY:
            logger.warning("MASTER_API_KEY is not set — you won't be able to bootstrap admin access")
        if settings.CORS_ORIGINS == "*":
            logger.warning("CORS_ORIGINS is open (*) — restrict in production")

    logger.info("Feature Flag Service ready")
    yield
    # ── shutdown ──────────────────────────────────────────────────────────
    await redis_cache.close()
    logger.info("Feature Flag Service stopped")


app = FastAPI(
    title="Feature Flag Service",
    version="1.0.0",
    docs_url="/docs" if settings.ENV != "production" else None,      # hide Swagger in prod
    redoc_url="/redoc" if settings.ENV != "production" else None,
    lifespan=lifespan,
)

# ── Exception handlers ────────────────────────────────────────────────────
register_exception_handlers(app)

# ── Middleware (outermost → innermost in execution order) ─────────────────
# Note: add_middleware stacks reverse, so last-added executes first.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(PrometheusMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

# Trusted Host (skip in dev to avoid localhost issues)
if settings.ENV != "development":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_host_list,
    )

# ── Routers ───────────────────────────────────────────────────────────────
app.include_router(flags.router)
app.include_router(api_keys.router)

# ── Observability endpoints (no auth required) ───────────────────────────
app.routes.append(Route("/metrics", metrics_endpoint, methods=["GET"]))


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok"}


@app.get("/health", tags=["health"])
async def health_check():
    """Deep health check — verifies DB and Redis connectivity."""
    import sqlalchemy

    checks: dict = {"status": "ok", "db": "ok", "cache": "ok"}

    # Check DB
    try:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute(sqlalchemy.text("SELECT 1"))
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
