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

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "*"                # comma-separated origins or "*"

    # ── Trusted hosts ─────────────────────────────────────────────────────
    ALLOWED_HOSTS: str = "*"               # comma-separated or "*"

    # ── Database pool ─────────────────────────────────────────────────────
    DB_POOL_SIZE: int = 10
    DB_POOL_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600            # recycle connections every hour

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        if self.ALLOWED_HOSTS.strip() == "*":
            return ["*"]
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]


settings = Settings()
