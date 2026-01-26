"""Scheduler worker for sending scheduled messages."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db.repositories import ContactRepository, ScheduledMessageRepository
from app.db.session import async_session_maker
from app.services import MessageService

logger = logging.getLogger(__name__)

# Check for due messages every 10 seconds
CHECK_INTERVAL_SECONDS = 10


async def calculate_next_cron_occurrence(
    cron_expression: str,
    from_time: datetime | None = None,
) -> datetime | None:
    """Calculate next occurrence from a cron expression.

    Simple implementation supporting: minute hour day month weekday
    For more complex cron, consider using croniter library.
    """
    try:
        from croniter import croniter

        base = from_time or datetime.now(timezone.utc)
        cron = croniter(cron_expression, base)
        return cron.get_next(datetime)
    except ImportError:
        # Fallback: schedule for same time tomorrow
        logger.warning("croniter not installed, using simple daily recurrence")
        base = from_time or datetime.now(timezone.utc)
        return base + timedelta(days=1)
    except Exception as e:
        logger.error(f"Error parsing cron expression '{cron_expression}': {e}")
        return None


async def process_due_messages() -> int:
    """Process all due scheduled messages. Returns count of messages sent."""
    sent_count = 0

    async with async_session_maker() as db:
        schedule_repo = ScheduledMessageRepository(db)
        contact_repo = ContactRepository(db)

        # Get all due messages
        due_messages = await schedule_repo.get_due_messages(limit=100)

        if not due_messages:
            return 0

        logger.info(f"Found {len(due_messages)} due messages to send")

        for scheduled in due_messages:
            try:
                # Get contact for phone number
                contact = await contact_repo.get(scheduled.contact_id)
                if not contact:
                    logger.error(
                        f"Contact {scheduled.contact_id} not found for scheduled message {scheduled.id}"
                    )
                    continue

                # Create message service for this device
                service = MessageService(db, scheduled.device_id)

                # Send the message
                await service.send_message(
                    phone=contact.phone_number,
                    content=scheduled.content,
                    content_type=scheduled.content_type,
                    media_url=scheduled.media_url,
                )

                logger.info(
                    f"Sent scheduled message {scheduled.id} to {contact.phone_number}"
                )

                # Mark as sent
                await schedule_repo.mark_as_sent(scheduled.id)
                sent_count += 1

                # Handle recurring messages
                if scheduled.is_recurring and scheduled.cron_expression:
                    next_time = await calculate_next_cron_occurrence(
                        scheduled.cron_expression,
                        scheduled.scheduled_at,
                    )
                    if next_time:
                        # Create new scheduled message for next occurrence
                        await schedule_repo.create(
                            device_id=scheduled.device_id,
                            contact_id=scheduled.contact_id,
                            scheduled_at=next_time,
                            content_type=scheduled.content_type,
                            content=scheduled.content,
                            media_url=scheduled.media_url,
                            is_recurring=True,
                            cron_expression=scheduled.cron_expression,
                        )
                        logger.info(
                            f"Created next recurring message for {next_time.isoformat()}"
                        )

            except Exception as e:
                logger.error(f"Error sending scheduled message {scheduled.id}: {e}")
                continue

    return sent_count


async def main() -> None:
    """Main scheduler loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting scheduler worker...")
    logger.info(f"Checking for due messages every {CHECK_INTERVAL_SECONDS} seconds")

    while True:
        try:
            sent_count = await process_due_messages()
            if sent_count > 0:
                logger.info(f"Processed {sent_count} scheduled messages")
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
