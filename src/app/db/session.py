from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings

_pool_kwargs = {}
# SQLite doesn't support pool_size / max_overflow
if "sqlite" not in settings.DATABASE_URL:
    _pool_kwargs = {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_POOL_MAX_OVERFLOW,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_pre_ping": True,          # verify connections are alive before use
    }

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    echo=False,
    **_pool_kwargs,
)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
