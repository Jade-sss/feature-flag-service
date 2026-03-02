from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.flag import FeatureFlagCreate, FeatureFlagRead, FeatureFlagUpdate
from app.db.session import AsyncSessionLocal
from app.db.repositories.flag_repository import FlagRepository
from app.services.evaluator import Evaluator

router = APIRouter(prefix="/flags", tags=["flags"])

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session

@router.post("/", response_model=FeatureFlagRead)
async def create_flag(payload: FeatureFlagCreate, session: AsyncSession = Depends(get_session)):
    repo = FlagRepository(session)
    existing = await repo.get_by_key(payload.key)
    if existing:
        raise HTTPException(status_code=400, detail="Flag key exists")
    obj = await repo.create(payload)
    return obj

@router.get("/", response_model=List[FeatureFlagRead])
async def list_flags(limit: int = 100, offset: int = 0, session: AsyncSession = Depends(get_session)):
    repo = FlagRepository(session)
    return await repo.list(limit=limit, offset=offset)

@router.get("/{key}", response_model=FeatureFlagRead)
async def get_flag(key: str, session: AsyncSession = Depends(get_session)):
    repo = FlagRepository(session)
    obj = await repo.get_by_key(key)
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

@router.patch("/{key}", response_model=FeatureFlagRead)
async def update_flag(key: str, payload: FeatureFlagUpdate, session: AsyncSession = Depends(get_session)):
    repo = FlagRepository(session)
    obj = await repo.update(key, payload)
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

@router.delete("/{key}")
async def delete_flag(key: str, session: AsyncSession = Depends(get_session)):
    repo = FlagRepository(session)
    ok = await repo.delete(key)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}

@router.get("/evaluate")
async def evaluate_flag(key: str = Query(...), user_id: Optional[str] = Query(None), session: AsyncSession = Depends(get_session)):
    evaluator = Evaluator(session)
    result = await evaluator.evaluate(key, user_id)
    return {"key": key, "user_id": user_id, "enabled": result}
