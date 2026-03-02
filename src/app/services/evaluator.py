import hashlib
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories.flag_repository import FlagRepository

def _user_hash_pct(user_id: str) -> int:
    h = hashlib.sha1(user_id.encode()).hexdigest()
    return int(h[:8], 16) % 100

class Evaluator:
    def __init__(self, session: AsyncSession):
        self.repo = FlagRepository(session)

    async def evaluate(self, flag_key: str, user_id: Optional[str] = None) -> bool:
        flag = await self.repo.get_by_key(flag_key)
        if not flag:
            return False
        # check per-user override
        if user_id:
            override = await self.repo.get_override(flag.id, user_id)
            if override is not None:
                return bool(override.enabled)
        # explicit global enabled
        if flag.is_enabled:
            return True
        # percentage rollout
        if flag.rollout_percentage:
            if not user_id:
                return False
            return _user_hash_pct(user_id) < int(flag.rollout_percentage)
        # otherwise disabled
        return False
