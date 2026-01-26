"""Agent model for AI/rule-based message handlers."""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class Agent(Base, TimestampMixin):
    """Represents an AI or rule-based agent for handling messages."""

    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    agent_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "langgraph" or "rule_based"

    # For rule-based agents: keyword triggers and response templates
    # For LangGraph agents: graph configuration
    config: Mapped[dict] = mapped_column(JSONB, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Higher priority agents run first

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="agents")  # noqa: F821
