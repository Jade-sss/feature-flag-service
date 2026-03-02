from typing import Optional
from pydantic import BaseModel, ConfigDict


class APIKeyCreate(BaseModel):
    name: str
    role: str = "readonly"  # "admin" or "readonly"


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
