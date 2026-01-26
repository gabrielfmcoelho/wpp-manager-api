"""Unit tests for MessageRepository."""

import pytest

from app.db.repositories import MessageRepository
from app.models import Message
from app.models.message import MessageDirection, MessageStatus


class TestMessageRepository:
    """Tests for MessageRepository."""

    @pytest.mark.asyncio
    async def test_update_status_by_whatsapp_id(self, db_session, sample_device):
        """Test updating message status by WhatsApp message ID."""
        repo = MessageRepository(db_session)

        # Create a message with WhatsApp ID
        message = Message(
            device_id=sample_device.id,
            contact_id=sample_device.id,  # Using device ID as contact for simplicity
            whatsapp_message_id="WHATSAPP123456",
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.SENT,
            content="Test message",
        )
        db_session.add(message)
        await db_session.commit()

        # Update status
        updated = await repo.update_status_by_whatsapp_id(
            "WHATSAPP123456", "delivered"
        )

        assert updated is not None
        assert updated.status == MessageStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_update_status_by_whatsapp_id_to_read(self, db_session, sample_device):
        """Test updating message status to read."""
        repo = MessageRepository(db_session)

        message = Message(
            device_id=sample_device.id,
            contact_id=sample_device.id,
            whatsapp_message_id="MSG_READ_TEST",
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.DELIVERED,
            content="Test message",
        )
        db_session.add(message)
        await db_session.commit()

        updated = await repo.update_status_by_whatsapp_id("MSG_READ_TEST", "read")

        assert updated is not None
        assert updated.status == MessageStatus.READ

    @pytest.mark.asyncio
    async def test_update_status_by_whatsapp_id_not_found(self, db_session):
        """Test updating status for non-existent message."""
        repo = MessageRepository(db_session)

        result = await repo.update_status_by_whatsapp_id(
            "NONEXISTENT_MSG_ID", "delivered"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_by_whatsapp_id_invalid_status(
        self, db_session, sample_device
    ):
        """Test updating with invalid status is handled gracefully."""
        repo = MessageRepository(db_session)

        message = Message(
            device_id=sample_device.id,
            contact_id=sample_device.id,
            whatsapp_message_id="MSG_INVALID_STATUS",
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.SENT,
            content="Test message",
        )
        db_session.add(message)
        await db_session.commit()

        # Invalid status should not raise, just return the message unchanged
        result = await repo.update_status_by_whatsapp_id(
            "MSG_INVALID_STATUS", "invalid_status"
        )

        # Should return the message but status unchanged
        assert result is not None
        assert result.status == MessageStatus.SENT

    @pytest.mark.asyncio
    async def test_get_by_whatsapp_id(self, db_session, sample_device):
        """Test getting message by WhatsApp ID."""
        repo = MessageRepository(db_session)

        message = Message(
            device_id=sample_device.id,
            contact_id=sample_device.id,
            whatsapp_message_id="GET_BY_WA_ID_TEST",
            direction=MessageDirection.INBOUND,
            status=MessageStatus.PENDING,
            content="Test message",
        )
        db_session.add(message)
        await db_session.commit()

        found = await repo.get_by_whatsapp_id(
            sample_device.id, "GET_BY_WA_ID_TEST"
        )

        assert found is not None
        assert found.whatsapp_message_id == "GET_BY_WA_ID_TEST"

    @pytest.mark.asyncio
    async def test_update_status(self, db_session, sample_device):
        """Test updating message status by message ID."""
        repo = MessageRepository(db_session)

        message = Message(
            device_id=sample_device.id,
            contact_id=sample_device.id,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            content="Test message",
        )
        db_session.add(message)
        await db_session.commit()

        updated = await repo.update_status(message.id, MessageStatus.SENT)

        assert updated is not None
        assert updated.status == MessageStatus.SENT
