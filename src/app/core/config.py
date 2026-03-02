from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/featureflags"
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_FLAG_TTL: int = 300      # seconds — flag data cache
    CACHE_EVAL_TTL: int = 60       # seconds — evaluation result cache
    ENV: str = "development"

    # ── Auth ──────────────────────────────────────────────────────────────
    MASTER_API_KEY: Optional[str] = None   # bootstrap admin key (set via env var)
    AUTH_ENABLED: bool = True              # disable auth entirely for local dev

    # ── Rate limiting ─────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 100         # max requests per window per IP
    RATE_LIMIT_WINDOW: int = 60            # sliding window in seconds

    # ── Logging ───────────────────────────────────────────────────────────
    LOG_FORMAT: str = "text"               # "json" for production, "text" for dev
    LOG_LEVEL: str = "INFO"


settings = Settings()
