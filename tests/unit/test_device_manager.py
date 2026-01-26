"""Unit tests for DeviceManager service."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.services.device_manager import DeviceManager


class TestDeviceManager:
    """Tests for DeviceManager service."""

    @pytest.mark.asyncio
    async def test_register_device(self, db_session):
        """Test registering a new device."""
        manager = DeviceManager(db_session)

        device = await manager.register_device("My Test Device")

        assert device is not None
        assert device.name == "My Test Device"
        assert device.is_active is True
        assert device.is_connected is False

    @pytest.mark.asyncio
    async def test_get_device(self, db_session, sample_device):
        """Test getting an existing device."""
        manager = DeviceManager(db_session)

        device = await manager.get_device(sample_device.id)

        assert device.id == sample_device.id
        assert device.name == sample_device.name

    @pytest.mark.asyncio
    async def test_get_device_not_found(self, db_session):
        """Test getting a non-existent device raises NotFoundError."""
        manager = DeviceManager(db_session)
        fake_id = uuid4()

        with pytest.raises(NotFoundError) as exc_info:
            await manager.get_device(fake_id)

        assert "Device" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_initiate_login(self, db_session, sample_device, mock_whatsapp_client):
        """Test initiating login returns QR data."""
        manager = DeviceManager(db_session)

        with patch(
            "app.services.device_manager.WhatsAppClient",
            return_value=mock_whatsapp_client,
        ):
            result = await manager.initiate_login(sample_device.id)

        assert "device_id" in result
        assert "qr" in result
        assert result["device_name"] == sample_device.name
        mock_whatsapp_client.get_qr_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_status_connected(self, db_session, sample_device, mock_whatsapp_client):
        """Test syncing status updates device with WhatsApp info."""
        manager = DeviceManager(db_session)

        with patch(
            "app.services.device_manager.WhatsAppClient",
            return_value=mock_whatsapp_client,
        ):
            device = await manager.sync_status(sample_device.id)

        assert device.is_connected is True
        assert device.whatsapp_id == "5511999999999@s.whatsapp.net"
        assert device.phone_number == "5511999999999"

    @pytest.mark.asyncio
    async def test_sync_status_disconnected(self, db_session, sample_device):
        """Test syncing status when device is disconnected."""
        manager = DeviceManager(db_session)
        mock_client = AsyncMock()
        mock_client.get_status = AsyncMock(
            return_value={"connected": False, "logged_in": False}
        )

        with patch(
            "app.services.device_manager.WhatsAppClient",
            return_value=mock_client,
        ):
            device = await manager.sync_status(sample_device.id)

        assert device.is_connected is False

    @pytest.mark.asyncio
    async def test_sync_status_api_error(self, db_session, sample_device):
        """Test syncing status marks device disconnected on API error."""
        manager = DeviceManager(db_session)
        mock_client = AsyncMock()
        mock_client.get_status = AsyncMock(
            side_effect=Exception("API Error")
        )

        # First set device as connected
        sample_device.is_connected = True
        await db_session.commit()

        with patch(
            "app.services.device_manager.WhatsAppClient",
            return_value=mock_client,
        ):
            device = await manager.sync_status(sample_device.id)

        assert device.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect_device(self, db_session, sample_device, mock_whatsapp_client):
        """Test disconnecting a device."""
        manager = DeviceManager(db_session)

        # Set device as connected
        sample_device.is_connected = True
        await db_session.commit()

        with patch(
            "app.services.device_manager.WhatsAppClient",
            return_value=mock_whatsapp_client,
        ):
            device = await manager.disconnect_device(sample_device.id)

        assert device.is_connected is False
        mock_whatsapp_client.logout.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_device(self, db_session, sample_device, mock_whatsapp_client):
        """Test deactivating a device."""
        manager = DeviceManager(db_session)

        with patch(
            "app.services.device_manager.WhatsAppClient",
            return_value=mock_whatsapp_client,
        ):
            device = await manager.deactivate_device(sample_device.id)

        assert device.is_active is False
        assert device.is_connected is False

    @pytest.mark.asyncio
    async def test_reactivate_device(self, db_session, sample_device):
        """Test reactivating a device."""
        manager = DeviceManager(db_session)

        # First deactivate
        sample_device.is_active = False
        await db_session.commit()

        device = await manager.reactivate_device(sample_device.id)

        assert device.is_active is True

    @pytest.mark.asyncio
    async def test_get_connection_info(self, db_session, sample_device, mock_whatsapp_client):
        """Test getting connection info."""
        manager = DeviceManager(db_session)

        with patch(
            "app.services.device_manager.WhatsAppClient",
            return_value=mock_whatsapp_client,
        ):
            info = await manager.get_connection_info(sample_device.id)

        assert info["device_id"] == str(sample_device.id)
        assert info["name"] == sample_device.name
        assert "websocket_url" in info
        assert "live_status" in info
