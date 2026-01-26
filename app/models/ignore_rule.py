"""Ignore rule model for filtering incoming messages."""

from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class IgnoreRuleType(str, Enum):
    """Ignore rule type enum."""

    CONTACT = "contact"
    GROUP = "group"
    KEYWORD = "keyword"


class IgnoreRule(Base, TimestampMixin):
    """Represents a rule for ignoring incoming messages."""

    __tablename__ = "ignore_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id"), nullable=False)

    rule_type: Mapped[IgnoreRuleType] = mapped_column(SQLEnum(IgnoreRuleType), nullable=False)
    pattern: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # JID, group name pattern, or keyword
    reason: Mapped[str | None] = mapped_column(String(255))

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="ignore_rules")  # noqa: F821
