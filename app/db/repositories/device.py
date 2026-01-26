"""Device repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models import Device


class DeviceRepository(BaseRepository[Device]):
    """Repository for device operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Device)

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        is_active: bool | None = None,
    ) -> tuple[list[Device], int]:
        """List devices with optional filtering."""
        # Build base query
        base_query = select(Device)

        if is_active is not None:
            base_query = base_query.where(Device.is_active == is_active)

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get items
        stmt = base_query.order_by(Device.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_by_whatsapp_id(self, whatsapp_id: str) -> Device | None:
        """Get device by WhatsApp ID."""
        stmt = select(Device).where(Device.whatsapp_id == whatsapp_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_connection_status(
        self, device_id: UUID, is_connected: bool
    ) -> Device | None:
        """Update device connection status."""
        device = await self.get(device_id)
        if device:
            device.is_connected = is_connected
            await self.session.commit()
            await self.session.refresh(device)
        return device

    async def update_whatsapp_info(
        self,
        device_id: UUID,
        *,
        whatsapp_id: str | None = None,
        phone_number: str | None = None,
        is_connected: bool | None = None,
    ) -> Device | None:
        """Update device WhatsApp information after successful login."""
        device = await self.get(device_id)
        if device:
            if whatsapp_id is not None:
                device.whatsapp_id = whatsapp_id
            if phone_number is not None:
                device.phone_number = phone_number
            if is_connected is not None:
                device.is_connected = is_connected
            await self.session.commit()
            await self.session.refresh(device)
        return device

    async def get_active_devices(self) -> list[Device]:
        """Get all active devices for WebSocket connections."""
        stmt = select(Device).where(Device.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_ids(
        self,
        *,
        device_ids: list[UUID],
        skip: int = 0,
        limit: int = 50,
        is_active: bool | None = None,
    ) -> tuple[list[Device], int]:
        """List devices filtered by specific IDs."""
        if not device_ids:
            return [], 0

        # Build base query
        base_query = select(Device).where(Device.id.in_(device_ids))

        if is_active is not None:
            base_query = base_query.where(Device.is_active == is_active)

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get items
        stmt = base_query.order_by(Device.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total
