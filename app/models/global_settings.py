"""Global settings model for application-wide configuration."""

from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin


class GlobalSettings(Base, TimestampMixin):
    """Store global application settings like OpenAI configuration."""

    __tablename__ = "global_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
