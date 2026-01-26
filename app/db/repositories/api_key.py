"""API key repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models import ApiKey


class ApiKeyRepository(BaseRepository[ApiKey]):
    """Repository for API key operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ApiKey)

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        device_id: UUID | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[ApiKey], int]:
        """List API keys with optional filtering."""
        # Build base query
        base_query = select(ApiKey)

        if device_id:
            base_query = base_query.where(ApiKey.device_id == device_id)

        if is_active is not None:
            base_query = base_query.where(ApiKey.is_active == is_active)

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get items
        stmt = base_query.order_by(ApiKey.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_by_prefix(self, key_prefix: str) -> list[ApiKey]:
        """Get API keys by prefix."""
        stmt = select(ApiKey).where(
            ApiKey.key_prefix == key_prefix,
            ApiKey.is_active == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def revoke(self, api_key_id: UUID) -> ApiKey | None:
        """Revoke an API key."""
        api_key = await self.get(api_key_id)
        if api_key:
            api_key.is_active = False
            await self.session.commit()
            await self.session.refresh(api_key)
        return api_key
