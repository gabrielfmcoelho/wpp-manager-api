"""Conversation repository for managing conversation state."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models import Conversation


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for conversation operations including agent state management."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Conversation)

    async def get_active_for_contact(
        self, device_id: UUID, contact_id: UUID
    ) -> Conversation | None:
        """Get the active conversation for a contact on a device.

        Args:
            device_id: The device ID
            contact_id: The contact ID

        Returns:
            The active conversation or None if not found
        """
        stmt = select(Conversation).where(
            Conversation.device_id == device_id,
            Conversation.contact_id == contact_id,
            Conversation.status == "active",
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_for_contact(
        self, device_id: UUID, contact_id: UUID
    ) -> tuple[Conversation, bool]:
        """Get existing active conversation or create a new one.

        Args:
            device_id: The device ID
            contact_id: The contact ID

        Returns:
            Tuple of (conversation, created) where created is True if new
        """
        existing = await self.get_active_for_contact(device_id, contact_id)
        if existing:
            return existing, False

        conversation = await self.create(
            device_id=device_id,
            contact_id=contact_id,
            status="active",
            agent_state={},
        )
        return conversation, True

    async def update_agent_state(
        self, conversation_id: UUID, agent_state: dict
    ) -> Conversation | None:
        """Update the agent state for a conversation.

        Args:
            conversation_id: The conversation ID
            agent_state: The new agent state dict

        Returns:
            The updated conversation or None if not found
        """
        conversation = await self.get(conversation_id)
        if conversation:
            conversation.agent_state = agent_state
            await self.session.commit()
            await self.session.refresh(conversation)
        return conversation

    async def close_conversation(self, conversation_id: UUID) -> Conversation | None:
        """Close a conversation so agents no longer respond.

        Args:
            conversation_id: The conversation ID

        Returns:
            The closed conversation or None if not found
        """
        conversation = await self.get(conversation_id)
        if conversation:
            conversation.status = "closed"
            await self.session.commit()
            await self.session.refresh(conversation)
        return conversation

    async def get_by_device_and_contact(
        self, device_id: UUID, contact_id: UUID, status: str | None = None
    ) -> Conversation | None:
        """Get a conversation by device and contact, optionally filtered by status.

        Args:
            device_id: The device ID
            contact_id: The contact ID
            status: Optional status filter

        Returns:
            The conversation or None if not found
        """
        stmt = select(Conversation).where(
            Conversation.device_id == device_id,
            Conversation.contact_id == contact_id,
        )
        if status:
            stmt = stmt.where(Conversation.status == status)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
