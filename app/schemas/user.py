"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.user_device import DeviceRole


class UserDetail(BaseModel):
    """Schema for user details."""

    id: UUID
    logto_sub: str
    email: str | None
    name: str | None
    picture: str | None
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserDeviceAssign(BaseModel):
    """Schema for assigning a device to a user."""

    device_id: UUID
    role: DeviceRole = Field(default=DeviceRole.VIEWER)


class UserDeviceResponse(BaseModel):
    """Schema for user-device relationship response."""

    id: UUID
    user_id: UUID
    device_id: UUID
    role: DeviceRole
    device_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserDeviceList(BaseModel):
    """Schema for list of user devices."""

    items: list[UserDeviceResponse]
    total: int
