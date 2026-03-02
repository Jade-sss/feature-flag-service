from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


# ── Feature Flag schemas ─────────────────────────────────────────────────────

class FeatureFlagBase(BaseModel):
    key: str = Field(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9._-]+$")
    description: Optional[str] = Field(None, max_length=2000)
    is_enabled: Optional[bool] = False
    rollout_percentage: Optional[int] = Field(None, ge=0, le=100)
    conditions: Optional[dict] = None

class FeatureFlagCreate(FeatureFlagBase):
    pass

class FeatureFlagUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=2000)
    is_enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = Field(None, ge=0, le=100)
    conditions: Optional[dict] = None

class FeatureFlagRead(FeatureFlagBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ── Per-user Override schemas ─────────────────────────────────────────────────

class FlagOverrideCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=200)
    enabled: bool

class FlagOverrideRead(BaseModel):
    id: int
    flag_id: int
    user_id: str
    enabled: bool
    model_config = ConfigDict(from_attributes=True)
