"""Contact model for WhatsApp contacts."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class Contact(Base, TimestampMixin):
    """Represents a WhatsApp contact."""

    __tablename__ = "contacts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id"), nullable=False)

    whatsapp_jid: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., 5511999999999@s.whatsapp.net
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    push_name: Mapped[str | None] = mapped_column(String(255))

    is_group: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="contacts")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        back_populates="contact", cascade="all, delete-orphan"
    )
    scheduled_messages: Mapped[list["ScheduledMessage"]] = relationship(  # noqa: F821
        back_populates="contact", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(  # noqa: F821
        back_populates="contact", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_contacts_device_jid", "device_id", "whatsapp_jid", unique=True),
        Index("ix_contacts_phone", "phone_number"),
    )
