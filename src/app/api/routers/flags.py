from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.flag import (
    FeatureFlagCreate, FeatureFlagRead, FeatureFlagUpdate,
    FlagOverrideCreate, FlagOverrideRead,
)
from app.db.session import AsyncSessionLocal
from app.db.repositories.flag_repository import FlagRepository
from app.services.evaluator import Evaluator
from app.cache import redis_cache

router = APIRouter(prefix="/flags", tags=["flags"])


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


# ── Evaluation (before /{key} so it doesn't get shadowed) ────────────────

@router.get("/evaluate", summary="Evaluate flag for a user")
async def evaluate_flag(
    key: str = Query(..., description="Flag key"),
    user_id: Optional[str] = Query(None, description="User ID for per-user evaluation"),
    session: AsyncSession = Depends(get_session),
):
    evaluator = Evaluator(session)
    result = await evaluator.evaluate(key, user_id)
    return {"key": key, "user_id": user_id, "enabled": result}


# ── Flag CRUD ─────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=FeatureFlagRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a feature flag",
)
async def create_flag(
    payload: FeatureFlagCreate,
    session: AsyncSession = Depends(get_session),
):
    repo = FlagRepository(session)
    existing = await repo.get_by_key(payload.key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Flag with key '{payload.key}' already exists",
        )
    obj = await repo.create(payload)
    await redis_cache.invalidate_flag(payload.key)
    return obj


@router.get("/", response_model=List[FeatureFlagRead], summary="List all flags")
async def list_flags(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    repo = FlagRepository(session)
    return await repo.list(limit=limit, offset=offset)


@router.get("/{key}", response_model=FeatureFlagRead, summary="Get a flag by key")
async def get_flag(key: str, session: AsyncSession = Depends(get_session)):
    repo = FlagRepository(session)
    obj = await repo.get_by_key(key)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")
    return obj


@router.patch("/{key}", response_model=FeatureFlagRead, summary="Update a flag")
async def update_flag(
    key: str,
    payload: FeatureFlagUpdate,
    session: AsyncSession = Depends(get_session),
):
    repo = FlagRepository(session)
    obj = await repo.update(key, payload)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")
    await redis_cache.invalidate_flag(key)
    return obj


@router.delete(
    "/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a flag",
)
async def delete_flag(key: str, session: AsyncSession = Depends(get_session)):
    repo = FlagRepository(session)
    ok = await repo.delete(key)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")
    await redis_cache.invalidate_flag(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Per-user Override management ──────────────────────────────────────────

@router.get(
    "/{key}/overrides",
    response_model=List[FlagOverrideRead],
    summary="List per-user overrides for a flag",
)
async def list_overrides(key: str, session: AsyncSession = Depends(get_session)):
    repo = FlagRepository(session)
    flag = await repo.get_by_key(key)
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")
    return await repo.list_overrides(flag.id)


@router.put(
    "/{key}/overrides/{user_id}",
    response_model=FlagOverrideRead,
    summary="Set override for a specific user (enable/disable)",
)
async def set_override(
    key: str,
    user_id: str,
    payload: FlagOverrideCreate,
    session: AsyncSession = Depends(get_session),
):
    repo = FlagRepository(session)
    flag = await repo.get_by_key(key)
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")
    override = await repo.set_override(flag.id, user_id, payload.enabled)
    await redis_cache.invalidate_flag(key)
    return override


@router.delete(
    "/{key}/overrides/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove per-user override",
)
async def delete_override(
    key: str,
    user_id: str,
    session: AsyncSession = Depends(get_session),
):
    repo = FlagRepository(session)
    flag = await repo.get_by_key(key)
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")
    ok = await repo.delete_override(flag.id, user_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No override for user '{user_id}' on flag '{key}'",
        )
    await redis_cache.invalidate_flag(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
