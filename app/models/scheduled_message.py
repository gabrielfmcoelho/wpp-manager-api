"""Scheduled message model for future message delivery."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class ScheduledMessage(Base, TimestampMixin):
    """Represents a message scheduled for future delivery."""

    __tablename__ = "scheduled_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id"), nullable=False)
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), nullable=False)

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    content_type: Mapped[str] = mapped_column(String(50), default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[str | None] = mapped_column(String(500))

    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    cron_expression: Mapped[str | None] = mapped_column(String(100))

    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="scheduled_messages")  # noqa: F821
    contact: Mapped["Contact"] = relationship(back_populates="scheduled_messages")  # noqa: F821

    __table_args__ = (
        Index("ix_scheduled_messages_scheduled_at", "scheduled_at"),
        Index("ix_scheduled_messages_device", "device_id"),
    )
