from typing import Optional
from pydantic import BaseModel

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
    class Config:
        orm_mode = True
