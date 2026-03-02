from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/featureflags"
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_FLAG_TTL: int = 300      # seconds — flag data cache
    CACHE_EVAL_TTL: int = 60       # seconds — evaluation result cache
    ENV: str = "development"

settings = Settings()
