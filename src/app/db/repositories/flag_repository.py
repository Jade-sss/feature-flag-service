from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.feature_flag import FeatureFlag, FlagOverride
from app.schemas.flag import FeatureFlagCreate, FeatureFlagUpdate

class FlagRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Flag CRUD ─────────────────────────────────────────────────────────

    async def create(self, payload: FeatureFlagCreate) -> FeatureFlag:
        obj = FeatureFlag(**payload.model_dump())
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def get_by_key(self, key: str) -> Optional[FeatureFlag]:
        q = select(FeatureFlag).where(FeatureFlag.key == key)
        res = await self.session.execute(q)
        return res.scalar_one_or_none()

    async def list(self, limit: int = 100, offset: int = 0) -> List[FeatureFlag]:
        q = select(FeatureFlag).limit(limit).offset(offset)
        res = await self.session.execute(q)
        return res.scalars().all()

    async def update(self, key: str, payload: FeatureFlagUpdate) -> Optional[FeatureFlag]:
        obj = await self.get_by_key(key)
        if not obj:
            return None
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, key: str) -> bool:
        obj = await self.get_by_key(key)
        if not obj:
            return False
        await self.session.delete(obj)
        return True

    # ── Per-user Override CRUD ────────────────────────────────────────────

    async def get_override(self, flag_id: int, user_id: str) -> Optional[FlagOverride]:
        q = select(FlagOverride).where(
            FlagOverride.flag_id == flag_id,
            FlagOverride.user_id == user_id,
        )
        res = await self.session.execute(q)
        return res.scalar_one_or_none()

    async def list_overrides(self, flag_id: int) -> List[FlagOverride]:
        q = select(FlagOverride).where(FlagOverride.flag_id == flag_id)
        res = await self.session.execute(q)
        return res.scalars().all()

    async def set_override(
        self, flag_id: int, user_id: str, enabled: bool
    ) -> FlagOverride:
        existing = await self.get_override(flag_id, user_id)
        if existing:
            existing.enabled = enabled
            self.session.add(existing)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        obj = FlagOverride(flag_id=flag_id, user_id=user_id, enabled=enabled)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete_override(self, flag_id: int, user_id: str) -> bool:
        existing = await self.get_override(flag_id, user_id)
        if not existing:
            return False
        await self.session.delete(existing)
        return True
