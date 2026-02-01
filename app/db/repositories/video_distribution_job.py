"""Video distribution job repository."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models import VideoDistributionJob


class VideoDistributionJobRepository(BaseRepository[VideoDistributionJob]):
    """Repository for video distribution job operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, VideoDistributionJob)

    async def get_by_agent(self, agent_id: UUID) -> VideoDistributionJob | None:
        """Get the distribution job for a specific agent.

        Args:
            agent_id: The agent's UUID.

        Returns:
            The job if found, None otherwise.
        """
        stmt = select(VideoDistributionJob).where(
            VideoDistributionJob.agent_id == agent_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        agent_id: UUID,
        initial_next_run: datetime | None = None,
    ) -> VideoDistributionJob:
        """Get existing job or create a new one for an agent.

        Args:
            agent_id: The agent's UUID.
            initial_next_run: When to schedule the first run (if creating).

        Returns:
            The existing or newly created job.
        """
        job = await self.get_by_agent(agent_id)
        if job is None:
            job = await self.create(
                agent_id=agent_id,
                next_run_at=initial_next_run or datetime.now(timezone.utc),
            )
        return job

    async def get_due_jobs(self, limit: int = 50) -> list[VideoDistributionJob]:
        """Get jobs that are due for execution.

        Args:
            limit: Maximum number of jobs to return.

        Returns:
            List of jobs where next_run_at is in the past.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(VideoDistributionJob)
            .where(
                VideoDistributionJob.next_run_at <= now,
                VideoDistributionJob.next_run_at.isnot(None),
            )
            .order_by(VideoDistributionJob.next_run_at)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_run_times(
        self,
        job: VideoDistributionJob,
        last_run: datetime,
        next_run: datetime,
    ) -> VideoDistributionJob:
        """Update the run timestamps for a job.

        Args:
            job: The job to update.
            last_run: When the job was last run.
            next_run: When the job should run next.

        Returns:
            The updated job.
        """
        job.last_run_at = last_run
        job.next_run_at = next_run
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def delete_by_agent(self, agent_id: UUID) -> bool:
        """Delete the job for a specific agent.

        Args:
            agent_id: The agent's UUID.

        Returns:
            True if a job was deleted, False otherwise.
        """
        job = await self.get_by_agent(agent_id)
        if job:
            await self.delete(job)
            return True
        return False
