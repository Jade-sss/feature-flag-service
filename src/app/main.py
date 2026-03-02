from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routers import flags
from app.api.routers import api_keys
from app.cache import redis_cache
from app.middleware.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await redis_cache.connect()
    yield
    # shutdown
    await redis_cache.close()


app = FastAPI(title="Feature Flag Service", lifespan=lifespan)

# ── Middleware (outermost first) ──────────────────────────────────────────
app.add_middleware(RateLimitMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────
app.include_router(flags.router)
app.include_router(api_keys.router)


@app.get("/")
async def root():
    return {"status": "ok"}
