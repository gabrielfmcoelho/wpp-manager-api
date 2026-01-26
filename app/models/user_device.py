"""UserDevice association model for user-device relationships."""

from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class DeviceRole(str, Enum):
    """Role a user has for a device."""

    OWNER = "owner"
    ADMIN = "admin"
    VIEWER = "viewer"


class UserDevice(Base, TimestampMixin):
    """Association table linking users to devices with roles."""

    __tablename__ = "user_devices"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id"), nullable=False)
    role: Mapped[DeviceRole] = mapped_column(
        SQLEnum(DeviceRole), default=DeviceRole.VIEWER, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="user_devices")  # noqa: F821
    device: Mapped["Device"] = relationship(back_populates="user_devices")  # noqa: F821

    __table_args__ = (
        Index("ix_user_devices_user_device", "user_id", "device_id", unique=True),
    )
