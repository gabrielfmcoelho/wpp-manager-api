"""UserDevice repository for user-device relationship operations."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories.base import BaseRepository
from app.models import Device, UserDevice
from app.models.user_device import DeviceRole


class UserDeviceRepository(BaseRepository[UserDevice]):
    """Repository for user-device relationship operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, UserDevice)

    async def create(
        self,
        user_id: UUID,
        device_id: UUID,
        role: DeviceRole = DeviceRole.VIEWER,
    ) -> UserDevice:
        """Create a new user-device relationship."""
        user_device = UserDevice(
            user_id=user_id,
            device_id=device_id,
            role=role,
        )
        self.session.add(user_device)
        await self.session.commit()
        await self.session.refresh(user_device)
        return user_device

    async def list_by_user(
        self,
        user_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[UserDevice], int]:
        """List all devices for a user with pagination."""
        # Count total
        count_stmt = (
            select(func.count())
            .select_from(UserDevice)
            .where(UserDevice.user_id == user_id)
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get items with device relationship loaded
        stmt = (
            select(UserDevice)
            .where(UserDevice.user_id == user_id)
            .options(selectinload(UserDevice.device))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_by_user_and_device(
        self,
        user_id: UUID,
        device_id: UUID,
    ) -> UserDevice | None:
        """Get a specific user-device relationship."""
        stmt = select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.device_id == device_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_user_and_device(
        self,
        user_id: UUID,
        device_id: UUID,
    ) -> bool:
        """Delete a user-device relationship. Returns True if deleted."""
        stmt = delete(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.device_id == device_id,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_user_device_ids(self, user_id: UUID) -> list[UUID]:
        """Get list of device IDs accessible to a user."""
        stmt = select(UserDevice.device_id).where(UserDevice.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def user_has_device_access(
        self,
        user_id: UUID,
        device_id: UUID,
    ) -> bool:
        """Check if a user has access to a device."""
        stmt = (
            select(func.count())
            .select_from(UserDevice)
            .where(
                UserDevice.user_id == user_id,
                UserDevice.device_id == device_id,
            )
        )
        result = await self.session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def get_user_device_role(
        self,
        user_id: UUID,
        device_id: UUID,
    ) -> DeviceRole | None:
        """Get the user's role for a specific device."""
        stmt = select(UserDevice.role).where(
            UserDevice.user_id == user_id,
            UserDevice.device_id == device_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
