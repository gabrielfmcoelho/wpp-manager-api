"""Scheduled message schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ScheduledMessageBase(BaseModel):
    """Base scheduled message schema."""

    content_type: str = Field(default="text", max_length=50)
    content: str = Field(..., min_length=1)
    media_url: str | None = Field(None, max_length=500)


class ScheduledMessageCreate(ScheduledMessageBase):
    """Schema for creating a scheduled message."""

    contact_id: UUID
    scheduled_at: datetime
    is_recurring: bool = False
    cron_expression: str | None = Field(None, max_length=100)


class ScheduledMessageUpdate(BaseModel):
    """Schema for updating a scheduled message."""

    scheduled_at: datetime | None = None
    content: str | None = Field(None, min_length=1)
    content_type: str | None = Field(None, max_length=50)
    media_url: str | None = Field(None, max_length=500)
    is_recurring: bool | None = None
    cron_expression: str | None = Field(None, max_length=100)
    is_cancelled: bool | None = None


class ScheduledMessageDetail(BaseModel):
    """Schema for scheduled message details."""

    id: UUID
    device_id: UUID
    contact_id: UUID
    scheduled_at: datetime
    sent_at: datetime | None
    content_type: str
    content: str
    media_url: str | None
    is_recurring: bool
    cron_expression: str | None
    is_cancelled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScheduledMessageList(BaseModel):
    """Schema for paginated scheduled message list."""

    items: list[ScheduledMessageDetail]
    total: int
    skip: int
    limit: int
