"""Message repository."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models import Message
from app.models.message import MessageDirection, MessageStatus


class MessageRepository(BaseRepository[Message]):
    """Repository for message operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Message)

    async def list(
        self,
        *,
        device_id: UUID,
        skip: int = 0,
        limit: int = 50,
        contact_id: UUID | None = None,
        direction: MessageDirection | None = None,
        status: MessageStatus | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> tuple[list[Message], int]:
        """List messages for a device with optional filtering."""
        # Build base query
        base_query = select(Message).where(Message.device_id == device_id)

        if contact_id:
            base_query = base_query.where(Message.contact_id == contact_id)

        if direction:
            base_query = base_query.where(Message.direction == direction)

        if status:
            base_query = base_query.where(Message.status == status)

        if after:
            base_query = base_query.where(Message.created_at >= after)

        if before:
            base_query = base_query.where(Message.created_at <= before)

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get items (most recent first)
        stmt = base_query.order_by(Message.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_by_device(self, device_id: UUID, message_id: UUID) -> Message | None:
        """Get a message ensuring it belongs to the device."""
        stmt = select(Message).where(
            Message.id == message_id,
            Message.device_id == device_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_whatsapp_id(
        self, device_id: UUID, whatsapp_message_id: str
    ) -> Message | None:
        """Get message by WhatsApp message ID."""
        stmt = select(Message).where(
            Message.device_id == device_id,
            Message.whatsapp_message_id == whatsapp_message_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self, message_id: UUID, status: MessageStatus
    ) -> Message | None:
        """Update message status."""
        message = await self.get(message_id)
        if message:
            message.status = status
            await self.session.commit()
            await self.session.refresh(message)
        return message

    async def update_status_by_whatsapp_id(
        self, whatsapp_message_id: str, status: str
    ) -> Message | None:
        """Update message status by WhatsApp message ID."""
        stmt = select(Message).where(Message.whatsapp_message_id == whatsapp_message_id)
        result = await self.session.execute(stmt)
        message = result.scalar_one_or_none()

        if message:
            try:
                message.status = MessageStatus(status)
                await self.session.commit()
                await self.session.refresh(message)
            except ValueError:
                # Invalid status value, ignore
                pass
        return message
