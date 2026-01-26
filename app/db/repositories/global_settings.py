"""Repository for global settings operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.global_settings import GlobalSettings


class GlobalSettingsRepository(BaseRepository[GlobalSettings]):
    """Repository for managing global settings."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, GlobalSettings)

    async def get_by_key(self, key: str) -> GlobalSettings | None:
        """Get settings by key."""
        stmt = select(GlobalSettings).where(GlobalSettings.key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, key: str, value: dict) -> GlobalSettings:
        """Create or update settings by key."""
        existing = await self.get_by_key(key)
        if existing:
            return await self.update(existing, value=value)
        return await self.create(key=key, value=value)
