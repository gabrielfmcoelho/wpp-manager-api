"""Integration tests for WebSocket listener worker."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestDeviceConnection:
    """Tests for DeviceConnection class."""

    @pytest.mark.asyncio
    async def test_handle_message_event_publishes_to_queue(
        self, sample_websocket_message_event
    ):
        """Test that message events are published to RabbitMQ."""
        from app.workers.websocket_listener import DeviceConnection

        device_id = uuid4()
        connection = DeviceConnection(device_id, "Test Device")

        with patch(
            "app.workers.websocket_listener.publish_incoming_message"
        ) as mock_publish:
            mock_publish.return_value = None
            await connection.handle_event(sample_websocket_message_event)

        mock_publish.assert_called_once_with(
            device_id, sample_websocket_message_event["data"]
        )

    @pytest.mark.asyncio
    async def test_handle_connected_event_updates_status(
        self, db_session, sample_device, sample_websocket_connected_event
    ):
        """Test that connected events update device status."""
        from app.workers.websocket_listener import DeviceConnection

        connection = DeviceConnection(sample_device.id, sample_device.name)

        with patch(
            "app.workers.websocket_listener.async_session_maker"
        ) as mock_session_maker:
            mock_session_maker.return_value.__aenter__.return_value = db_session

            await connection.handle_event(sample_websocket_connected_event)

        # Refresh to get updated status
        await db_session.refresh(sample_device)
        assert sample_device.is_connected is True

    @pytest.mark.asyncio
    async def test_handle_disconnected_event_updates_status(
        self, db_session, sample_device
    ):
        """Test that disconnected events update device status."""
        from app.workers.websocket_listener import DeviceConnection

        # First set as connected
        sample_device.is_connected = True
        await db_session.commit()

        connection = DeviceConnection(sample_device.id, sample_device.name)
        event = {"event": "disconnected", "data": {}}

        with patch(
            "app.workers.websocket_listener.async_session_maker"
        ) as mock_session_maker:
            mock_session_maker.return_value.__aenter__.return_value = db_session

            await connection.handle_event(event)

        await db_session.refresh(sample_device)
        assert sample_device.is_connected is False

    @pytest.mark.asyncio
    async def test_handle_message_ack_event(
        self, db_session, sample_device, sample_websocket_ack_event
    ):
        """Test that message ack events update message status."""
        from app.models import Message
        from app.models.message import MessageDirection, MessageStatus
        from app.workers.websocket_listener import DeviceConnection

        # Create a message
        message = Message(
            device_id=sample_device.id,
            contact_id=sample_device.id,
            whatsapp_message_id="ABCD1234567890",
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.SENT,
            content="Test",
        )
        db_session.add(message)
        await db_session.commit()

        connection = DeviceConnection(sample_device.id, sample_device.name)

        with patch(
            "app.workers.websocket_listener.async_session_maker"
        ) as mock_session_maker:
            mock_session_maker.return_value.__aenter__.return_value = db_session

            await connection.handle_event(sample_websocket_ack_event)

        await db_session.refresh(message)
        assert message.status == MessageStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_get_websocket_url(self):
        """Test WebSocket URL generation in connection."""
        from app.workers.websocket_listener import DeviceConnection

        device_id = uuid4()
        connection = DeviceConnection(device_id, "Test Device")

        url = connection.client.get_websocket_url()

        assert "ws://" in url or "wss://" in url
        assert str(device_id) in url


class TestWebSocketManager:
    """Tests for WebSocketManager class."""

    @pytest.mark.asyncio
    async def test_add_device_creates_connection(self):
        """Test that adding a device creates a connection."""
        from app.workers.websocket_listener import WebSocketManager

        manager = WebSocketManager()
        device_id = uuid4()

        # Mock the listen method to avoid actual connection
        with patch(
            "app.workers.websocket_listener.DeviceConnection.listen",
            new_callable=AsyncMock,
        ):
            await manager.add_device(device_id, "Test Device")

        assert device_id in manager.connections
        assert device_id in manager.tasks

        # Cleanup
        await manager.close()

    @pytest.mark.asyncio
    async def test_add_device_skips_duplicate(self):
        """Test that adding the same device twice is skipped."""
        from app.workers.websocket_listener import WebSocketManager

        manager = WebSocketManager()
        device_id = uuid4()

        with patch(
            "app.workers.websocket_listener.DeviceConnection.listen",
            new_callable=AsyncMock,
        ):
            await manager.add_device(device_id, "Test Device")
            await manager.add_device(device_id, "Test Device")

        assert len(manager.connections) == 1

        await manager.close()

    @pytest.mark.asyncio
    async def test_remove_device_closes_connection(self):
        """Test that removing a device closes the connection."""
        from app.workers.websocket_listener import WebSocketManager

        manager = WebSocketManager()
        device_id = uuid4()

        with patch(
            "app.workers.websocket_listener.DeviceConnection.listen",
            new_callable=AsyncMock,
        ):
            await manager.add_device(device_id, "Test Device")
            await manager.remove_device(device_id)

        assert device_id not in manager.connections
        assert device_id not in manager.tasks

    @pytest.mark.asyncio
    async def test_load_devices_from_database(self, db_session, sample_device):
        """Test loading active devices from database."""
        from app.workers.websocket_listener import WebSocketManager

        manager = WebSocketManager()

        with patch(
            "app.workers.websocket_listener.async_session_maker"
        ) as mock_session_maker:
            mock_session_maker.return_value.__aenter__.return_value = db_session

            devices = await manager.load_devices()

        assert len(devices) >= 1
        device_ids = [d[0] for d in devices]
        assert sample_device.id in device_ids

    @pytest.mark.asyncio
    async def test_close_removes_all_connections(self):
        """Test that close removes all connections."""
        from app.workers.websocket_listener import WebSocketManager

        manager = WebSocketManager()

        with patch(
            "app.workers.websocket_listener.DeviceConnection.listen",
            new_callable=AsyncMock,
        ):
            await manager.add_device(uuid4(), "Device 1")
            await manager.add_device(uuid4(), "Device 2")

        assert len(manager.connections) == 2

        await manager.close()

        assert len(manager.connections) == 0
        assert len(manager.tasks) == 0
