"""Video send history model for tracking sent videos per contact."""

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class VideoSendHistory(Base, TimestampMixin):
    """Tracks which videos have been sent to which contacts per agent."""

    __tablename__ = "video_send_history"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    video_filename: Mapped[str] = mapped_column(String(500), nullable=False)

    # Relationships
    agent: Mapped["Agent"] = relationship()  # noqa: F821
    contact: Mapped["Contact"] = relationship()  # noqa: F821

    __table_args__ = (
        # Unique constraint: each video can only be sent once per contact per agent
        Index(
            "ix_video_send_history_unique",
            "agent_id",
            "contact_id",
            "video_filename",
            unique=True,
        ),
        Index("ix_video_send_history_agent", "agent_id"),
        Index("ix_video_send_history_contact", "contact_id"),
    )
