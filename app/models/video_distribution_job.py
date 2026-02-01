"""Video distribution job model for tracking distribution schedule state."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class VideoDistributionJob(Base, TimestampMixin):
    """Tracks distribution schedule state per video_distributor agent."""

    __tablename__ = "video_distribution_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    agent: Mapped["Agent"] = relationship()  # noqa: F821

    __table_args__ = (
        Index("ix_video_distribution_jobs_next_run", "next_run_at"),
    )
