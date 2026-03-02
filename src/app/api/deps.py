"""
Authentication dependencies for FastAPI routes.

Two levels of access:
  require_any_key  — any valid, active API key (admin or readonly)
  require_admin    — only admin-role keys

A bootstrap MASTER_API_KEY env var allows initial admin access before
any keys are created in the database.
"""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.api_key import APIKey, APIKeyRole, hash_api_key
from app.db.repositories.api_key_repository import APIKeyRepository
from app.db.session import get_session

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _resolve_api_key(
    raw_key: str | None = Security(API_KEY_HEADER),
    session: AsyncSession = Depends(get_session),
) -> APIKey:
    """Validate the X-API-Key header and return the corresponding record.

    When AUTH_ENABLED is False (local dev), every request is treated as admin.
    Also accepts the MASTER_API_KEY for bootstrapping.
    """
    # Auth disabled → treat as admin
    if not settings.AUTH_ENABLED:
        return APIKey(
            id=0, key_hash="noauth", key_prefix="noauth",
            name="__noauth__", role=APIKeyRole.admin, is_active=True,
        )

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    # Check master key first (always admin)
    if settings.MASTER_API_KEY and raw_key == settings.MASTER_API_KEY:
        # Return a synthetic admin record (not persisted)
        fake = APIKey(
            id=0,
            key_hash="master",
            key_prefix="master",
            name="__master__",
            role=APIKeyRole.admin,
            is_active=True,
        )
        return fake

    # Look up in DB
    repo = APIKeyRepository(session)
    key_hash = hash_api_key(raw_key)
    record = await repo.get_by_hash(key_hash)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )
    return record


async def require_any_key(
    api_key: APIKey = Depends(_resolve_api_key),
) -> APIKey:
    """Dependency: any valid key (admin or readonly)."""
    return api_key


async def require_admin(
    api_key: APIKey = Depends(_resolve_api_key),
) -> APIKey:
    """Dependency: only admin-role keys."""
    if api_key.role != APIKeyRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return api_key
