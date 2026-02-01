"""Video send history repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models import VideoSendHistory


class VideoSendHistoryRepository(BaseRepository[VideoSendHistory]):
    """Repository for video send history operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, VideoSendHistory)

    async def get_sent_videos_for_contact(
        self,
        agent_id: UUID,
        contact_id: UUID,
    ) -> list[str]:
        """Get list of video filenames already sent to a contact.

        Args:
            agent_id: The agent's UUID.
            contact_id: The contact's UUID.

        Returns:
            List of video filenames that have been sent.
        """
        stmt = select(VideoSendHistory.video_filename).where(
            VideoSendHistory.agent_id == agent_id,
            VideoSendHistory.contact_id == contact_id,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def record_video_sent(
        self,
        agent_id: UUID,
        contact_id: UUID,
        video_filename: str,
    ) -> VideoSendHistory:
        """Record that a video was sent to a contact.

        Args:
            agent_id: The agent's UUID.
            contact_id: The contact's UUID.
            video_filename: The filename of the video sent.

        Returns:
            The created VideoSendHistory record.
        """
        return await self.create(
            agent_id=agent_id,
            contact_id=contact_id,
            video_filename=video_filename,
        )

    async def reset_history_for_contact(
        self,
        agent_id: UUID,
        contact_id: UUID,
    ) -> int:
        """Reset the video history for a specific contact.

        This allows the cycle to restart with all videos available again.

        Args:
            agent_id: The agent's UUID.
            contact_id: The contact's UUID.

        Returns:
            Number of records deleted.
        """
        stmt = delete(VideoSendHistory).where(
            VideoSendHistory.agent_id == agent_id,
            VideoSendHistory.contact_id == contact_id,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def reset_history_for_agent(self, agent_id: UUID) -> int:
        """Reset all video history for an agent.

        Args:
            agent_id: The agent's UUID.

        Returns:
            Number of records deleted.
        """
        stmt = delete(VideoSendHistory).where(
            VideoSendHistory.agent_id == agent_id,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount
