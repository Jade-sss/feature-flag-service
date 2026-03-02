from typing import Optional
from pydantic import BaseModel, ConfigDict


# ── Feature Flag schemas ─────────────────────────────────────────────────────

class FeatureFlagBase(BaseModel):
    key: str
    description: Optional[str] = None
    is_enabled: Optional[bool] = False
    rollout_percentage: Optional[int] = None
    conditions: Optional[dict] = None

class FeatureFlagCreate(FeatureFlagBase):
    pass

class FeatureFlagUpdate(BaseModel):
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = None
    conditions: Optional[dict] = None

class FeatureFlagRead(FeatureFlagBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ── Per-user Override schemas ─────────────────────────────────────────────────

class FlagOverrideCreate(BaseModel):
    user_id: str
    enabled: bool

class FlagOverrideRead(BaseModel):
    id: int
    flag_id: int
    user_id: str
    enabled: bool
    model_config = ConfigDict(from_attributes=True)
