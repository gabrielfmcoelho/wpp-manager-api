"""WebSocket listener worker for real-time WhatsApp API events."""

import asyncio
import json
import logging
from uuid import UUID

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from app.config import settings
from app.db.session import async_session_maker
from app.services import WhatsAppClient
from app.services.queue import publish_incoming_message

logger = logging.getLogger(__name__)


class DeviceConnection:
    """Manages a WebSocket connection for a single device."""

    def __init__(self, device_id: UUID, device_name: str):
        self.device_id = device_id
        self.device_name = device_name
        self.client = WhatsAppClient(str(device_id))
        self.websocket = None
        self.reconnect_delay = 1.0  # Initial delay in seconds
        self.max_reconnect_delay = 60.0
        self.running = True

    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        ws_url = self.client.get_websocket_url()
        auth_header = self.client.get_auth_header()

        extra_headers = auth_header if auth_header else {}

        try:
            self.websocket = await websockets.connect(
                ws_url,
                additional_headers=extra_headers,
                ping_interval=30,
                ping_timeout=10,
            )
            self.reconnect_delay = 1.0  # Reset delay on successful connection
            logger.info(f"Connected to WebSocket for device {self.device_name} ({self.device_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to connect WebSocket for device {self.device_name}: {e}")
            return False

    async def handle_event(self, event_data: dict) -> None:
        """Process a WebSocket event."""
        # WhatsApp API can send event type in different fields: event, type, or code
        event_type = (
            event_data.get("event")
            or event_data.get("type")
            or event_data.get("code")
            or "unknown"
        )
        data = event_data.get("data", event_data)

        logger.debug(f"Device {self.device_name} received event: {event_type}")

        if event_type in ("message", "message.received"):
            # Publish incoming message to RabbitMQ for processing
            await publish_incoming_message(self.device_id, data)
            logger.info(f"Message received on device {self.device_name}, published to queue")

        elif event_type in ("message.ack", "message.update"):
            # Message status update (sent, delivered, read)
            await self._handle_message_ack(data)

        elif event_type in ("connected", "ready"):
            await self._handle_connected()

        elif event_type in ("disconnected", "logout"):
            await self._handle_disconnected()

        elif event_type in ("login_success", "LOGIN_SUCCESS"):
            # Handle successful WhatsApp login
            # Message format: "Successfully pair with 558688418515:42@s.whatsapp.net"
            await self._handle_login_success(data)

        elif event_type in ("list_devices", "LIST_DEVICES"):
            # Handle device found/connected event
            # Message format: {"code":"LIST_DEVICES","message":"Device found","result":[{"name":"...","device":"...@s.whatsapp.net"}]}
            await self._handle_list_devices(data)

        elif event_type == "qr":
            # QR code event during login - just log it
            logger.info(f"QR code event for device {self.device_name}")

        else:
            logger.debug(f"Unhandled event type '{event_type}' for device {self.device_name}")

    async def _handle_message_ack(self, data: dict) -> None:
        """Handle message acknowledgment (status update)."""
        try:
            async with async_session_maker() as db:
                from app.db.repositories import MessageRepository

                message_id = data.get("id") or data.get("message_id")
                ack_type = data.get("ack") or data.get("status")

                if not message_id:
                    return

                # Map ack type to status
                status_map = {
                    1: "sent",
                    2: "delivered",
                    3: "read",
                    "sent": "sent",
                    "delivered": "delivered",
                    "read": "read",
                }
                status = status_map.get(ack_type)

                if status:
                    repo = MessageRepository(db)
                    await repo.update_status_by_whatsapp_id(message_id, status)
                    logger.debug(f"Updated message {message_id} status to {status}")

        except Exception as e:
            logger.error(f"Error handling message ack: {e}")

    async def _handle_connected(self) -> None:
        """Handle device connected event."""
        try:
            async with async_session_maker() as db:
                from app.db.repositories import DeviceRepository

                repo = DeviceRepository(db)
                await repo.update_connection_status(self.device_id, True)
                logger.info(f"Device {self.device_name} marked as connected")
        except Exception as e:
            logger.error(f"Error updating connection status: {e}")

    async def _handle_disconnected(self) -> None:
        """Handle device disconnected event."""
        try:
            async with async_session_maker() as db:
                from app.db.repositories import DeviceRepository

                repo = DeviceRepository(db)
                await repo.update_connection_status(self.device_id, False)
                logger.info(f"Device {self.device_name} marked as disconnected")
        except Exception as e:
            logger.error(f"Error updating connection status: {e}")

    async def _handle_login_success(self, data: dict) -> None:
        """Handle successful WhatsApp login event."""
        try:
            async with async_session_maker() as db:
                from app.db.repositories import DeviceRepository

                # Extract JID from message
                # Message format: "Successfully pair with 558688418515:42@s.whatsapp.net"
                message = data.get("message", "")
                jid = self._extract_jid_from_message(message)
                phone_number = None

                if jid and "@" in jid:
                    # Extract phone number from JID (format: 5511999999999:NN@s.whatsapp.net)
                    phone_part = jid.split("@")[0]
                    # Remove the :NN suffix if present
                    phone_number = phone_part.split(":")[0] if ":" in phone_part else phone_part

                repo = DeviceRepository(db)
                await repo.update_whatsapp_info(
                    self.device_id,
                    whatsapp_id=jid,
                    phone_number=phone_number,
                    is_connected=True,
                )
                logger.info(
                    f"Device {self.device_name} logged in successfully "
                    f"(JID: {jid}, Phone: {phone_number})"
                )
        except Exception as e:
            logger.error(f"Error handling login success: {e}")

    def _extract_jid_from_message(self, message: str) -> str | None:
        """Extract JID from login success message."""
        import re

        # Pattern to match JID in message
        # Examples:
        # "Successfully pair with 558688418515:42@s.whatsapp.net"
        # "Successfully paired with 5511999999999@s.whatsapp.net"
        pattern = r"(\d+(?::\d+)?@s\.whatsapp\.net)"
        match = re.search(pattern, message)
        return match.group(1) if match else None

    async def _handle_list_devices(self, data: dict) -> None:
        """Handle LIST_DEVICES event indicating device is connected."""
        try:
            async with async_session_maker() as db:
                from app.db.repositories import DeviceRepository

                # Extract device info from result
                # Format: {"code":"LIST_DEVICES","message":"Device found","result":[{"name":"...","device":"...@s.whatsapp.net"}]}
                result = data.get("result", [])
                if not result:
                    result = data.get("results", [])

                jid = None
                phone_number = None
                device_name = None

                if result and len(result) > 0:
                    device_info = result[0]
                    jid = device_info.get("device")
                    device_name = device_info.get("name")

                    if jid and "@" in jid:
                        # Extract phone number from JID
                        phone_part = jid.split("@")[0]
                        phone_number = phone_part.split(":")[0] if ":" in phone_part else phone_part

                repo = DeviceRepository(db)
                await repo.update_whatsapp_info(
                    self.device_id,
                    whatsapp_id=jid,
                    phone_number=phone_number,
                    is_connected=True,
                )
                logger.info(
                    f"Device {self.device_name} connected via LIST_DEVICES "
                    f"(JID: {jid}, Phone: {phone_number}, Name: {device_name})"
                )
        except Exception as e:
            logger.error(f"Error handling LIST_DEVICES: {e}")

    async def listen(self) -> None:
        """Listen for events on the WebSocket connection."""
        while self.running:
            try:
                if not self.websocket or self.websocket.closed:
                    if not await self.connect():
                        # Exponential backoff on connection failure
                        await asyncio.sleep(self.reconnect_delay)
                        self.reconnect_delay = min(
                            self.reconnect_delay * 2, self.max_reconnect_delay
                        )
                        continue

                # Receive and process messages
                async for raw_message in self.websocket:
                    try:
                        event_data = json.loads(raw_message)
                        await self.handle_event(event_data)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON received: {raw_message[:100]}")

            except ConnectionClosed as e:
                logger.warning(
                    f"WebSocket closed for device {self.device_name}: {e.code} - {e.reason}"
                )
                self.websocket = None
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

            except WebSocketException as e:
                logger.error(f"WebSocket error for device {self.device_name}: {e}")
                self.websocket = None
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

            except Exception as e:
                logger.error(f"Unexpected error for device {self.device_name}: {e}")
                self.websocket = None
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    async def close(self) -> None:
        """Close the WebSocket connection."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info(f"Closed WebSocket for device {self.device_name}")


class WebSocketManager:
    """Manages WebSocket connections for all active devices."""

    def __init__(self):
        self.connections: dict[UUID, DeviceConnection] = {}
        self.tasks: dict[UUID, asyncio.Task] = {}
        self.refresh_interval = 60  # Check for new devices every 60 seconds

    async def load_devices(self) -> list[tuple[UUID, str]]:
        """Load active devices from database."""
        async with async_session_maker() as db:
            from app.db.repositories import DeviceRepository

            repo = DeviceRepository(db)
            devices = await repo.get_active_devices()
            return [(d.id, d.name) for d in devices]

    async def add_device(self, device_id: UUID, device_name: str) -> None:
        """Add a new device connection."""
        if device_id in self.connections:
            return

        connection = DeviceConnection(device_id, device_name)
        self.connections[device_id] = connection

        task = asyncio.create_task(connection.listen())
        self.tasks[device_id] = task
        logger.info(f"Started WebSocket listener for device {device_name}")

    async def remove_device(self, device_id: UUID) -> None:
        """Remove a device connection."""
        if device_id not in self.connections:
            return

        connection = self.connections.pop(device_id)
        await connection.close()

        if device_id in self.tasks:
            task = self.tasks.pop(device_id)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info(f"Stopped WebSocket listener for device {device_id}")

    async def refresh_devices(self) -> None:
        """Refresh device list and add/remove connections as needed."""
        while True:
            try:
                devices = await self.load_devices()
                current_ids = set(self.connections.keys())
                new_ids = set(d[0] for d in devices)

                # Add new devices
                for device_id, device_name in devices:
                    if device_id not in current_ids:
                        await self.add_device(device_id, device_name)

                # Remove deleted/inactive devices
                for device_id in current_ids - new_ids:
                    await self.remove_device(device_id)

            except Exception as e:
                logger.error(f"Error refreshing devices: {e}")

            await asyncio.sleep(self.refresh_interval)

    async def run(self) -> None:
        """Run the WebSocket manager."""
        logger.info("Starting WebSocket manager...")

        # Initial device load
        devices = await self.load_devices()
        for device_id, device_name in devices:
            await self.add_device(device_id, device_name)

        logger.info(f"Loaded {len(devices)} active devices")

        # Start refresh loop
        refresh_task = asyncio.create_task(self.refresh_devices())

        try:
            # Wait for all tasks
            await asyncio.gather(refresh_task, *self.tasks.values(), return_exceptions=True)
        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup
            for device_id in list(self.connections.keys()):
                await self.remove_device(device_id)
            refresh_task.cancel()

    async def close(self) -> None:
        """Close all connections."""
        for device_id in list(self.connections.keys()):
            await self.remove_device(device_id)


async def main() -> None:
    """Main entry point for the WebSocket listener worker."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting WebSocket listener worker...")

    manager = WebSocketManager()

    try:
        await manager.run()
    except KeyboardInterrupt:
        logger.info("Shutting down WebSocket listener...")
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
