import hashlib
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories.flag_repository import FlagRepository
from app.cache import redis_cache
from app.middleware.prometheus import FLAG_EVALUATIONS


def _user_hash_pct(user_id: str) -> int:
    h = hashlib.sha1(user_id.encode()).hexdigest()
    return int(h[:8], 16) % 100


class Evaluator:
    def __init__(self, session: AsyncSession):
        self.repo = FlagRepository(session)

    async def evaluate(self, flag_key: str, user_id: Optional[str] = None) -> bool:
        # 1) check evaluation cache (per flag+user)
        if user_id:
            cached = await redis_cache.get_evaluation(flag_key, user_id)
            if cached is not None:
                FLAG_EVALUATIONS.labels(result=str(cached).lower()).inc()
                return cached

        # 2) load flag (try cache first, then DB)
        flag = await self.repo.get_by_key(flag_key)
        if not flag:
            FLAG_EVALUATIONS.labels(result="false").inc()
            return False

        # 3) check per-user override
        if user_id:
            override = await self.repo.get_override(flag.id, user_id)
            if override is not None:
                result = bool(override.enabled)
                await redis_cache.set_evaluation(flag_key, user_id, result)
                FLAG_EVALUATIONS.labels(result=str(result).lower()).inc()
                return result

        # 4) explicit global enabled
        if flag.is_enabled:
            result = True
        # 5) percentage rollout
        elif flag.rollout_percentage:
            if not user_id:
                FLAG_EVALUATIONS.labels(result="false").inc()
                return False
            result = _user_hash_pct(user_id) < int(flag.rollout_percentage)
        else:
            result = False

        # cache the evaluation result
        if user_id:
            await redis_cache.set_evaluation(flag_key, user_id, result)
        FLAG_EVALUATIONS.labels(result=str(result).lower()).inc()
        return result
