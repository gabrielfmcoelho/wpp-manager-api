"""Unit tests for DeviceRepository."""

import pytest

from app.db.repositories import DeviceRepository
from app.models import Device


class TestDeviceRepository:
    """Tests for DeviceRepository."""

    @pytest.mark.asyncio
    async def test_update_whatsapp_info_all_fields(self, db_session, sample_device):
        """Test updating all WhatsApp info fields."""
        repo = DeviceRepository(db_session)

        updated = await repo.update_whatsapp_info(
            sample_device.id,
            whatsapp_id="5511888888888@s.whatsapp.net",
            phone_number="5511888888888",
            is_connected=True,
        )

        assert updated.whatsapp_id == "5511888888888@s.whatsapp.net"
        assert updated.phone_number == "5511888888888"
        assert updated.is_connected is True

    @pytest.mark.asyncio
    async def test_update_whatsapp_info_partial(self, db_session, sample_device):
        """Test updating only some WhatsApp info fields."""
        repo = DeviceRepository(db_session)
        original_phone = sample_device.phone_number

        updated = await repo.update_whatsapp_info(
            sample_device.id,
            is_connected=True,
        )

        assert updated.is_connected is True
        assert updated.phone_number == original_phone  # Unchanged

    @pytest.mark.asyncio
    async def test_update_whatsapp_info_not_found(self, db_session):
        """Test updating WhatsApp info for non-existent device."""
        repo = DeviceRepository(db_session)
        from uuid import uuid4

        result = await repo.update_whatsapp_info(
            uuid4(),
            whatsapp_id="test@s.whatsapp.net",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_devices(self, db_session):
        """Test getting only active devices."""
        repo = DeviceRepository(db_session)

        # Create active device
        active_device = Device(name="Active Device", is_active=True)
        db_session.add(active_device)

        # Create inactive device
        inactive_device = Device(name="Inactive Device", is_active=False)
        db_session.add(inactive_device)

        await db_session.commit()

        active_devices = await repo.get_active_devices()

        assert len(active_devices) >= 1
        assert all(d.is_active for d in active_devices)
        assert any(d.name == "Active Device" for d in active_devices)
        assert not any(d.name == "Inactive Device" for d in active_devices)

    @pytest.mark.asyncio
    async def test_update_connection_status(self, db_session, sample_device):
        """Test updating connection status."""
        repo = DeviceRepository(db_session)

        # Initially disconnected
        assert sample_device.is_connected is False

        # Connect
        updated = await repo.update_connection_status(sample_device.id, True)
        assert updated.is_connected is True

        # Disconnect
        updated = await repo.update_connection_status(sample_device.id, False)
        assert updated.is_connected is False

    @pytest.mark.asyncio
    async def test_get_by_whatsapp_id(self, db_session, sample_device):
        """Test getting device by WhatsApp ID."""
        repo = DeviceRepository(db_session)

        device = await repo.get_by_whatsapp_id(sample_device.whatsapp_id)

        assert device is not None
        assert device.id == sample_device.id

    @pytest.mark.asyncio
    async def test_get_by_whatsapp_id_not_found(self, db_session):
        """Test getting device by non-existent WhatsApp ID."""
        repo = DeviceRepository(db_session)

        device = await repo.get_by_whatsapp_id("nonexistent@s.whatsapp.net")

        assert device is None
