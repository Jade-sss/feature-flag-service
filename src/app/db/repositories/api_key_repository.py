from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.api_key import APIKey, APIKeyRole, generate_api_key, hash_api_key


class APIKeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name: str, role: str = "readonly") -> tuple[APIKey, str]:
        """Create a new API key. Returns (db_record, raw_key)."""
        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key)
        obj = APIKey(
            key_hash=key_hash,
            key_prefix=raw_key[:8],
            name=name,
            role=APIKeyRole(role),
            is_active=True,
        )
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj, raw_key

    async def get_by_hash(self, key_hash: str) -> Optional[APIKey]:
        result = await self.session.execute(
            select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)
        )
        return result.scalars().first()

    async def list(self) -> List[APIKey]:
        result = await self.session.execute(
            select(APIKey).order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, key_id: int) -> bool:
        result = await self.session.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        obj = result.scalars().first()
        if not obj:
            return False
        obj.is_active = False
        await self.session.flush()
        return True
