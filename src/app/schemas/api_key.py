from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    role: Literal["admin", "readonly"] = "readonly"


class APIKeyRead(BaseModel):
    id: int
    key_prefix: str
    name: str
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class APIKeyCreated(APIKeyRead):
    """Returned only once on creation — includes the raw key."""
    raw_key: str
