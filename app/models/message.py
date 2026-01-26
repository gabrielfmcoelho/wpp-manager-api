"""Message model for WhatsApp messages."""

from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class MessageDirection(str, Enum):
    """Message direction enum."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, Enum):
    """Message status enum."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class Message(Base, TimestampMixin):
    """Represents a WhatsApp message."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id"), nullable=False)
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), nullable=False)
    conversation_id: Mapped[UUID | None] = mapped_column(ForeignKey("conversations.id"))

    whatsapp_message_id: Mapped[str | None] = mapped_column(String(100))

    direction: Mapped[MessageDirection] = mapped_column(
        SQLEnum(MessageDirection), nullable=False
    )
    status: Mapped[MessageStatus] = mapped_column(
        SQLEnum(MessageStatus), default=MessageStatus.PENDING
    )

    content_type: Mapped[str] = mapped_column(
        String(50), default="text"
    )  # text, image, audio, video, document
    content: Mapped[str | None] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(String(500))
    extra_data: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="messages")  # noqa: F821
    contact: Mapped["Contact"] = relationship(back_populates="messages")  # noqa: F821
    conversation: Mapped["Conversation | None"] = relationship(  # noqa: F821
        back_populates="messages"
    )

    __table_args__ = (
        Index("ix_messages_device_contact", "device_id", "contact_id"),
        Index("ix_messages_whatsapp_id", "whatsapp_message_id"),
        Index("ix_messages_created_at", "created_at"),
    )
