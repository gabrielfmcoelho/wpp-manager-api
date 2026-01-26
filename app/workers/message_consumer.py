"""RabbitMQ consumer worker for async message processing."""

import asyncio
import json
import logging
from uuid import UUID

import aio_pika

from app.config import settings
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)


async def process_message(message: aio_pika.IncomingMessage) -> None:
    """Process a single message from the queue."""
    async with message.process():
        try:
            data = json.loads(message.body.decode())
            device_id = UUID(data["device_id"])
            message_data = data["message"]

            logger.info(f"Processing message for device {device_id}")

            async with async_session_maker() as db:
                # Import here to avoid circular imports
                from app.db.repositories import IgnoreRuleRepository
                from app.services import MessageService

                # Check ignore rules first
                ignore_repo = IgnoreRuleRepository(db)
                if await ignore_repo.should_ignore(device_id, message_data):
                    logger.debug(f"Message ignored by rules for device {device_id}")
                    return

                # Process the message and get the contact
                service = MessageService(db, device_id)
                contact = await service.process_incoming_message(message_data)

                # Run agents if available
                try:
                    from app.services.agent_runner import run_agents

                    # Pass contact_id for stateful agent tracking
                    contact_id = contact.id if contact else None
                    response = await run_agents(
                        db, device_id, message_data, contact_id=contact_id
                    )
                    if response:
                        # Send agent response
                        sender_phone = message_data.get("from", "").replace(
                            "@s.whatsapp.net", ""
                        )
                        if sender_phone:
                            await service.send_message(
                                phone=sender_phone,
                                content=response,
                            )
                            logger.info(f"Agent response sent to {sender_phone}")
                except ImportError:
                    # Agent runner not yet implemented
                    logger.debug("Agent runner not available, skipping agent processing")
                except Exception as e:
                    logger.error(f"Error running agents: {e}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            raise


async def publish_message(device_id: UUID, message_data: dict) -> None:
    """Publish a message to the queue for processing."""
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


async def main() -> None:
    """Main consumer loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting message consumer worker...")

    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        queue = await channel.declare_queue("incoming_messages", durable=True)

        logger.info("Listening for messages on 'incoming_messages' queue...")
        await queue.consume(process_message)

        # Run forever
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
