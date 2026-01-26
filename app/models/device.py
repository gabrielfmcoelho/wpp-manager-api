"""Device model for WhatsApp connected devices."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class Device(Base, TimestampMixin):
    """Represents a connected WhatsApp device/account."""

    __tablename__ = "devices"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20))
    whatsapp_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        back_populates="device", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        back_populates="device", cascade="all, delete-orphan"
    )
    scheduled_messages: Mapped[list["ScheduledMessage"]] = relationship(  # noqa: F821
        back_populates="device", cascade="all, delete-orphan"
    )
    agents: Mapped[list["Agent"]] = relationship(  # noqa: F821
        back_populates="device", cascade="all, delete-orphan"
    )
    ignore_rules: Mapped[list["IgnoreRule"]] = relationship(  # noqa: F821
        back_populates="device", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(  # noqa: F821
        back_populates="device", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(  # noqa: F821
        back_populates="device", cascade="all, delete-orphan"
    )
    user_devices: Mapped[list["UserDevice"]] = relationship(  # noqa: F821
        back_populates="device", cascade="all, delete-orphan"
    )
