"""Contact schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ContactBase(BaseModel):
    """Base contact schema."""

    phone_number: str = Field(..., min_length=1, max_length=20)
    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, description="Optional description or notes about the contact")


class ContactCreate(ContactBase):
    """Schema for creating a new contact."""

    pass


class ContactUpdate(BaseModel):
    """Schema for updating a contact."""

    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, description="Optional description or notes about the contact")
    is_blocked: bool | None = None


class ContactDetail(BaseModel):
    """Schema for contact details."""

    id: UUID
    device_id: UUID
    whatsapp_jid: str
    phone_number: str
    name: str | None
    push_name: str | None
    description: str | None
    is_group: bool
    is_blocked: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactList(BaseModel):
    """Schema for paginated contact list."""

    items: list[ContactDetail]
    total: int
    skip: int
    limit: int
