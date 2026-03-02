from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.db.base import Base

class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=False, nullable=False)
    rollout_percentage = Column(Integer, nullable=True)  # 0-100 for percentage rollouts
    conditions = Column(JSON, nullable=True)  # targeting rules as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class FlagOverride(Base):
    __tablename__ = "flag_overrides"

    id = Column(Integer, primary_key=True, index=True)
    flag_id = Column(Integer, ForeignKey("feature_flags.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(200), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
