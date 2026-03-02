import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.base import Base
from app.db.models.feature_flag import FeatureFlag, FlagOverride  # noqa: F401 — ensure models registered
from app.db.models.api_key import APIKey as APIKeyModel  # noqa: F401 — ensure model registered
from app.core.config import settings
from app.main import app
from app.db.session import get_session

# Disable auth by default so existing functional tests still pass unchanged.
# The test_auth.py file re-enables it for auth-specific tests.
settings.AUTH_ENABLED = False

# In-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite://"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    """Create tables once per test session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def session_override():
    """Override the FastAPI get_session dependency with our test DB (auto-commit)."""
    async def _override():
        async with TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    app.dependency_overrides[get_session] = _override
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def clean_tables():
    """Wipe all rows between tests for isolation."""
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
