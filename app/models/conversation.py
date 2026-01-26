"""Conversation model for grouping related messages."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class Conversation(Base, TimestampMixin):
    """Represents a conversation thread with a contact."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id"), nullable=False)
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), nullable=False)

    status: Mapped[str] = mapped_column(
        String(50), default="active"
    )  # active, closed, pending
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Agent state storage for LangGraph
    agent_state: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="conversations")  # noqa: F821
    contact: Mapped["Contact"] = relationship(back_populates="conversations")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")  # noqa: F821

    __table_args__ = (
        Index("ix_conversations_device_contact", "device_id", "contact_id"),
        Index("ix_conversations_status", "status"),
    )
