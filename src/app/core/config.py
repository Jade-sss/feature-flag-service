from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/featureflags"
    REDIS_URL: str = "redis://localhost:6379/0"
    ENV: str = "development"

settings = Settings()
