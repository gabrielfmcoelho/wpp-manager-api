"""Device lifecycle management service."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, WhatsAppAPIError
from app.db.repositories import DeviceRepository
from app.models import Device
from app.services.whatsapp_client import WhatsAppClient

logger = logging.getLogger(__name__)


class DeviceManager:
    """Centralized service for device lifecycle management.

    Handles device registration, login/logout flows, and status synchronization
    with the WhatsApp API.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DeviceRepository(db)

    async def register_device(self, name: str) -> Device:
        """Register a new device in the system.

        Args:
            name: Human-readable name for the device

        Returns:
            The created Device instance
        """
        device = await self.repo.create(name=name)
        logger.info(f"Registered new device: {device.name} ({device.id})")
        return device

    async def get_device(self, device_id: UUID) -> Device:
        """Get a device by ID.

        Args:
            device_id: UUID of the device

        Returns:
            The Device instance

        Raises:
            NotFoundError: If device doesn't exist
        """
        device = await self.repo.get(device_id)
        if not device:
            raise NotFoundError("Device", str(device_id))
        return device

    async def initiate_login(self, device_id: UUID) -> dict:
        """Initiate QR code login for a device.

        Args:
            device_id: UUID of the device to login

        Returns:
            Dict containing QR code data from WhatsApp API

        Raises:
            NotFoundError: If device doesn't exist
            WhatsAppAPIError: If API call fails
        """
        device = await self.get_device(device_id)
        client = WhatsAppClient(str(device_id))

        qr_data = await client.get_qr_code()
        logger.info(f"Login initiated for device: {device.name} ({device_id})")

        return {
            "device_id": str(device_id),
            "device_name": device.name,
            "qr": qr_data,
        }

    async def sync_status(self, device_id: UUID) -> Device:
        """Synchronize device status from WhatsApp API.

        Fetches current status from WhatsApp API and updates local database
        with connection status, WhatsApp JID, and phone number.

        Args:
            device_id: UUID of the device

        Returns:
            Updated Device instance

        Raises:
            NotFoundError: If device doesn't exist
        """
        device = await self.get_device(device_id)
        client = WhatsAppClient(str(device_id))

        try:
            status = await client.get_status()

            is_connected = status.get("connected", False)
            is_logged_in = status.get("logged_in", False)
            jid = status.get("jid") or status.get("wid")

            # Extract phone number from JID
            phone_number = None
            if jid and "@" in jid:
                phone_number = jid.split("@")[0]

            # Update device info
            device = await self.repo.update_whatsapp_info(
                device_id,
                whatsapp_id=jid if jid else None,
                phone_number=phone_number,
                is_connected=is_connected and is_logged_in,
            )

            logger.info(
                f"Status synced for device {device.name}: "
                f"connected={device.is_connected}, jid={device.whatsapp_id}"
            )

        except WhatsAppAPIError as e:
            logger.warning(f"Failed to sync status for device {device_id}: {e}")
            # Mark as disconnected on API error
            device = await self.repo.update_connection_status(device_id, False)

        return device

    async def complete_login(self, device_id: UUID) -> Device:
        """Complete login after QR code scan.

        Should be called after user scans QR code to verify connection
        and save WhatsApp identity information.

        Args:
            device_id: UUID of the device

        Returns:
            Updated Device instance with WhatsApp info

        Raises:
            NotFoundError: If device doesn't exist
        """
        # Sync status to get JID and connection info
        device = await self.sync_status(device_id)

        if device.is_connected:
            logger.info(f"Login completed for device: {device.name} ({device_id})")
        else:
            logger.warning(f"Login not completed for device: {device.name} ({device_id})")

        return device

    async def disconnect_device(self, device_id: UUID) -> Device:
        """Disconnect/logout a device from WhatsApp.

        Args:
            device_id: UUID of the device

        Returns:
            Updated Device instance

        Raises:
            NotFoundError: If device doesn't exist
            WhatsAppAPIError: If logout fails
        """
        device = await self.get_device(device_id)
        client = WhatsAppClient(str(device_id))

        try:
            await client.logout()
            logger.info(f"Logout successful for device: {device.name} ({device_id})")
        except WhatsAppAPIError as e:
            logger.warning(f"Logout API call failed for device {device_id}: {e}")

        # Always update local status to disconnected
        device = await self.repo.update_connection_status(device_id, False)
        return device

    async def deactivate_device(self, device_id: UUID) -> Device:
        """Deactivate a device (soft delete).

        Disconnects from WhatsApp and marks device as inactive.

        Args:
            device_id: UUID of the device

        Returns:
            Updated Device instance

        Raises:
            NotFoundError: If device doesn't exist
        """
        # Disconnect first if connected
        device = await self.get_device(device_id)
        if device.is_connected:
            await self.disconnect_device(device_id)

        # Mark as inactive
        device = await self.repo.update(device, is_active=False)
        logger.info(f"Device deactivated: {device.name} ({device_id})")
        return device

    async def reactivate_device(self, device_id: UUID) -> Device:
        """Reactivate a previously deactivated device.

        Args:
            device_id: UUID of the device

        Returns:
            Updated Device instance

        Raises:
            NotFoundError: If device doesn't exist
        """
        device = await self.get_device(device_id)
        device = await self.repo.update(device, is_active=True)
        logger.info(f"Device reactivated: {device.name} ({device_id})")
        return device

    async def get_connection_info(self, device_id: UUID) -> dict:
        """Get detailed connection information for a device.

        Args:
            device_id: UUID of the device

        Returns:
            Dict with connection details
        """
        device = await self.get_device(device_id)
        client = WhatsAppClient(str(device_id))

        result = {
            "device_id": str(device.id),
            "name": device.name,
            "phone_number": device.phone_number,
            "whatsapp_id": device.whatsapp_id,
            "is_connected": device.is_connected,
            "is_active": device.is_active,
            "websocket_url": client.get_websocket_url(),
        }

        # Try to get live status
        try:
            status = await client.get_status()
            result["live_status"] = status
        except WhatsAppAPIError:
            result["live_status"] = None

        return result
