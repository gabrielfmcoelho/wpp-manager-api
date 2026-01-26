"""Device schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceBase(BaseModel):
    """Base device schema."""

    name: str = Field(..., min_length=1, max_length=100)


class DeviceCreate(DeviceBase):
    """Schema for creating a new device."""

    pass


class DeviceUpdate(BaseModel):
    """Schema for updating a device."""

    name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None


class DeviceDetail(DeviceBase):
    """Schema for device details."""

    id: UUID
    phone_number: str | None
    whatsapp_id: str | None
    is_connected: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceStatus(BaseModel):
    """Schema for device connection status."""

    id: UUID
    name: str
    is_connected: bool
    phone_number: str | None
    last_seen: datetime | None = None


class DeviceList(BaseModel):
    """Schema for paginated device list."""

    items: list[DeviceDetail]
    total: int
    skip: int
    limit: int
