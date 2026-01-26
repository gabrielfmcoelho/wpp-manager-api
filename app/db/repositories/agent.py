"""Agent repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models import Agent


class AgentRepository(BaseRepository[Agent]):
    """Repository for agent operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Agent)

    async def list(
        self,
        *,
        device_id: UUID,
        skip: int = 0,
        limit: int = 50,
        is_active: bool | None = None,
        agent_type: str | None = None,
    ) -> tuple[list[Agent], int]:
        """List agents for a device with optional filtering."""
        # Build base query
        base_query = select(Agent).where(Agent.device_id == device_id)

        if is_active is not None:
            base_query = base_query.where(Agent.is_active == is_active)

        if agent_type:
            base_query = base_query.where(Agent.agent_type == agent_type)

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get items (by priority, then name)
        stmt = (
            base_query.order_by(Agent.priority.desc(), Agent.name).offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_by_device(self, device_id: UUID, agent_id: UUID) -> Agent | None:
        """Get an agent ensuring it belongs to the device."""
        stmt = select(Agent).where(
            Agent.id == agent_id,
            Agent.device_id == device_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_for_device(self, device_id: UUID) -> list[Agent]:
        """Get all active agents for a device, ordered by priority (highest first)."""
        stmt = (
            select(Agent)
            .where(
                Agent.device_id == device_id,
                Agent.is_active == True,  # noqa: E712
            )
            .order_by(Agent.priority.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
