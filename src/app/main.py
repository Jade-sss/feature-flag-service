from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routers import flags
from app.cache import redis_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await redis_cache.connect()
    yield
    # shutdown
    await redis_cache.close()


app = FastAPI(title="Feature Flag Service", lifespan=lifespan)
app.include_router(flags.router)


@app.get("/")
async def root():
    return {"status": "ok"}
