"""Message schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.message import MessageDirection, MessageStatus


class MessageBase(BaseModel):
    """Base message schema."""

    content_type: str = Field(default="text", max_length=50)
    content: str | None = None
    media_url: str | None = Field(None, max_length=500)


class MessageCreate(BaseModel):
    """Schema for sending a new message."""

    phone: str = Field(..., description="Phone number to send to")
    content: str = Field(..., description="Message content")
    content_type: str = Field(default="text", description="Message type: text, image, audio, video, document")
    media_url: str | None = Field(None, description="URL for media content")


class MessageDetail(BaseModel):
    """Schema for message details."""

    id: UUID
    device_id: UUID
    contact_id: UUID
    conversation_id: UUID | None
    whatsapp_message_id: str | None
    direction: MessageDirection
    status: MessageStatus
    content_type: str
    content: str | None
    media_url: str | None
    extra_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageList(BaseModel):
    """Schema for paginated message list."""

    items: list[MessageDetail]
    total: int
    skip: int
    limit: int


class WebhookPayload(BaseModel):
    """Schema for WhatsApp webhook payload."""

    device_id: str
    event: str
    data: dict[str, Any]
