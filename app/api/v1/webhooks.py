"""Webhook endpoints for receiving WhatsApp events."""

import logging
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession, RedisClient
from app.db.repositories import DeviceRepository
from app.schemas import WebhookPayload
from app.services.queue import publish_incoming_message
from app.services.webhook_event_store import WebhookEventStore

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/whatsapp")
async def whatsapp_webhook(
    payload: WebhookPayload,
    db: DbSession,
    redis: RedisClient,
):
    """Receive webhooks from WhatsApp API server.

    Events:
    - message: Incoming message
    - message.ack: Message delivery/read status update
    - connected: Device connected
    - disconnected: Device disconnected
    - qr: QR code for login
    """
    # Store event immediately on receipt for debugging
    store = WebhookEventStore(redis)
    event_id = await store.store_event(
        device_id=payload.device_id,
        event_type=payload.event,
        payload=payload.data,
        status="received",
    )

    # Get device by WhatsApp ID or use the provided device_id
    device_repo = DeviceRepository(db)
    device = await device_repo.get_by_whatsapp_id(payload.device_id)

    if not device:
        # Try to find by UUID if it's a valid UUID
        try:
            device_uuid = UUID(payload.device_id)
            device = await device_repo.get(device_uuid)
        except ValueError:
            pass

    if not device:
        await store.update_status(event_id, "ignored", "unknown_device")
        return {"status": "ignored", "reason": "unknown_device", "event_id": event_id}

    try:
        # Handle different event types
        if payload.event == "message":
            # Push to RabbitMQ for async processing
            try:
                await publish_incoming_message(device.id, payload.data)
                logger.debug(f"Message queued for device {device.id}")
            except Exception as e:
                logger.error(f"Failed to queue message: {e}")
                # Fall through - message still acknowledged

        elif payload.event == "message.ack":
            # Update message status
            from app.db.repositories import MessageRepository
            from app.models.message import MessageStatus

            whatsapp_id = payload.data.get("id")
            ack = payload.data.get("ack", 0)

            # Map ack levels to status
            status_map = {
                1: MessageStatus.SENT,
                2: MessageStatus.DELIVERED,
                3: MessageStatus.READ,
            }

            if whatsapp_id and ack in status_map:
                msg_repo = MessageRepository(db)
                message = await msg_repo.get_by_whatsapp_id(device.id, whatsapp_id)
                if message:
                    await msg_repo.update_status(message.id, status_map[ack])

        elif payload.event == "connected":
            await device_repo.update_connection_status(device.id, True)

        elif payload.event == "disconnected":
            await device_repo.update_connection_status(device.id, False)

        # Update status on success
        await store.update_status(event_id, "processed")
        return {"status": "received", "event": payload.event, "event_id": event_id}

    except Exception as e:
        # Update status on error
        await store.update_status(event_id, "failed", str(e))
        logger.error(f"Error processing webhook: {e}")
        raise
