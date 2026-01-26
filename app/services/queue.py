"""Message queue service for RabbitMQ."""

import json
import logging
from uuid import UUID

import aio_pika

from app.config import settings

logger = logging.getLogger(__name__)


async def publish_incoming_message(device_id: UUID, message_data: dict) -> None:
    """Publish an incoming message to the queue for async processing."""
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        await channel.declare_queue("incoming_messages", durable=True)

        payload = {
            "device_id": str(device_id),
            "message": message_data,
        }

        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="incoming_messages",
        )
        logger.debug(f"Message published to queue for device {device_id}")
