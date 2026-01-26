"""API key schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApiKeyBase(BaseModel):
    """Base API key schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class ApiKeyCreate(ApiKeyBase):
    """Schema for creating an API key."""

    device_id: UUID
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    """Schema for API key creation response (includes the actual key)."""

    id: UUID
    name: str
    key: str  # The actual API key, only shown once on creation
    key_prefix: str
    device_id: UUID
    expires_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyDetail(BaseModel):
    """Schema for API key details (without the actual key)."""

    id: UUID
    name: str
    key_prefix: str
    device_id: UUID
    description: str | None
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApiKeyList(BaseModel):
    """Schema for paginated API key list."""

    items: list[ApiKeyDetail]
    total: int
    skip: int
    limit: int
