"""Ignore rule schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.ignore_rule import IgnoreRuleType


class IgnoreRuleBase(BaseModel):
    """Base ignore rule schema."""

    rule_type: IgnoreRuleType
    pattern: str = Field(..., min_length=1, max_length=255)
    reason: str | None = Field(None, max_length=255)


class IgnoreRuleCreate(IgnoreRuleBase):
    """Schema for creating an ignore rule."""

    pass


class IgnoreRuleDetail(BaseModel):
    """Schema for ignore rule details."""

    id: UUID
    device_id: UUID
    rule_type: IgnoreRuleType
    pattern: str
    reason: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IgnoreRuleList(BaseModel):
    """Schema for paginated ignore rule list."""

    items: list[IgnoreRuleDetail]
    total: int
    skip: int
    limit: int
