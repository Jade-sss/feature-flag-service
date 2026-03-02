"""
API Key management endpoints — admin only.

POST   /api-keys/        — create a new key (returns raw key once)
GET    /api-keys/        — list all keys (hashed, no raw values)
DELETE /api-keys/{id}    — revoke (soft-delete) a key
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.api_key import APIKeyCreate, APIKeyRead, APIKeyCreated
from app.db.repositories.api_key_repository import APIKeyRepository
from app.db.models.api_key import APIKey
from app.api.deps import require_admin
from app.db.session import get_session

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post(
    "/",
    response_model=APIKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key",
)
async def create_api_key(
    payload: APIKeyCreate,
    session: AsyncSession = Depends(get_session),
    _admin: APIKey = Depends(require_admin),
):
    repo = APIKeyRepository(session)
    record, raw_key = await repo.create(name=payload.name, role=payload.role)
    return APIKeyCreated(
        id=record.id,
        key_prefix=record.key_prefix,
        name=record.name,
        role=record.role.value,
        is_active=record.is_active,
        raw_key=raw_key,
    )


@router.get(
    "/",
    response_model=List[APIKeyRead],
    summary="List all API keys",
)
async def list_api_keys(
    session: AsyncSession = Depends(get_session),
    _admin: APIKey = Depends(require_admin),
):
    repo = APIKeyRepository(session)
    keys = await repo.list()
    return keys


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
)
async def revoke_api_key(
    key_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: APIKey = Depends(require_admin),
):
    repo = APIKeyRepository(session)
    ok = await repo.revoke(key_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
