"""Scheduled message repository."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models import ScheduledMessage


class ScheduledMessageRepository(BaseRepository[ScheduledMessage]):
    """Repository for scheduled message operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ScheduledMessage)

    async def list(
        self,
        *,
        device_id: UUID | None = None,
        device_ids: list[UUID] | None = None,
        skip: int = 0,
        limit: int = 50,
        contact_id: UUID | None = None,
        is_cancelled: bool | None = None,
        pending_only: bool = False,
    ) -> tuple[list[ScheduledMessage], int]:
        """List scheduled messages for device(s) with optional filtering."""
        # Build base query
        base_query = select(ScheduledMessage)

        # Filter by device(s)
        if device_id:
            base_query = base_query.where(ScheduledMessage.device_id == device_id)
        elif device_ids:
            base_query = base_query.where(ScheduledMessage.device_id.in_(device_ids))

        if contact_id:
            base_query = base_query.where(ScheduledMessage.contact_id == contact_id)

        if is_cancelled is not None:
            base_query = base_query.where(ScheduledMessage.is_cancelled == is_cancelled)

        if pending_only:
            base_query = base_query.where(
                ScheduledMessage.sent_at.is_(None),
                ScheduledMessage.is_cancelled == False,  # noqa: E712
            )

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get items (soonest first)
        stmt = base_query.order_by(ScheduledMessage.scheduled_at).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_by_device(
        self, device_id: UUID, scheduled_id: UUID
    ) -> ScheduledMessage | None:
        """Get a scheduled message ensuring it belongs to the device."""
        stmt = select(ScheduledMessage).where(
            ScheduledMessage.id == scheduled_id,
            ScheduledMessage.device_id == device_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_due_messages(self, limit: int = 100) -> list[ScheduledMessage]:
        """Get scheduled messages that are due for sending."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(ScheduledMessage)
            .where(
                ScheduledMessage.scheduled_at <= now,
                ScheduledMessage.sent_at.is_(None),
                ScheduledMessage.is_cancelled == False,  # noqa: E712
            )
            .order_by(ScheduledMessage.scheduled_at)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_as_sent(self, scheduled_id: UUID) -> ScheduledMessage | None:
        """Mark a scheduled message as sent."""
        scheduled = await self.get(scheduled_id)
        if scheduled:
            scheduled.sent_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(scheduled)
        return scheduled

    async def cancel(self, scheduled_id: UUID) -> ScheduledMessage | None:
        """Cancel a scheduled message."""
        scheduled = await self.get(scheduled_id)
        if scheduled:
            scheduled.is_cancelled = True
            await self.session.commit()
            await self.session.refresh(scheduled)
        return scheduled
