"""
API Key model for token-based authentication.

Roles:
  admin    — full CRUD on flags, overrides, and API keys
  readonly — read flags + evaluate only
"""

import secrets
import hashlib
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.sql import func
from app.db.base import Base

import enum


class APIKeyRole(str, enum.Enum):
    admin = "admin"
    readonly = "readonly"


def generate_api_key() -> str:
    """Generate a cryptographically secure API key (48 URL-safe chars)."""
    return secrets.token_urlsafe(36)


def hash_api_key(raw: str) -> str:
    """One-way SHA-256 hash so we never store plaintext keys."""
    return hashlib.sha256(raw.encode()).hexdigest()


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    key_prefix = Column(String(8), nullable=False)  # first 8 chars for display
    name = Column(String(200), nullable=False)
    role = Column(SAEnum(APIKeyRole), nullable=False, default=APIKeyRole.readonly)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
