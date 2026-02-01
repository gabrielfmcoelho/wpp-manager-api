"""Video distributor worker for sending videos to subscribers."""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from app.agents.video_distributor import VideoDistributorAgent
from app.db.repositories import (
    AgentRepository,
    ContactRepository,
    ScheduledMessageRepository,
    VideoDistributionJobRepository,
    VideoSendHistoryRepository,
)
from app.db.session import async_session_maker
from app.services.minio_client import get_minio_client

logger = logging.getLogger(__name__)

# Check for due jobs every 60 seconds
CHECK_INTERVAL_SECONDS = 60


async def process_distribution_job(
    agent_id: UUID,
    device_id: UUID,
    config: dict,
) -> int:
    """Process a single video distribution job.

    Args:
        agent_id: The agent's UUID.
        device_id: The device's UUID.
        config: The agent's configuration.

    Returns:
        Number of videos scheduled for distribution.
    """
    scheduled_count = 0

    # Create agent instance
    agent = VideoDistributorAgent(config)

    # Check if within active hours
    if not agent.is_within_active_hours():
        logger.debug(f"Agent {agent_id} outside active hours, skipping")
        return 0

    # Get MinIO client and list videos
    minio_client = get_minio_client()
    bucket_name = config.get("bucket_name", "")

    if not bucket_name:
        logger.warning(f"Agent {agent_id} has no bucket_name configured")
        return 0

    try:
        all_videos = minio_client.get_video_filenames(bucket_name)
    except Exception as e:
        logger.error(f"Error listing videos from bucket {bucket_name}: {e}")
        return 0

    if not all_videos:
        logger.warning(f"No videos found in bucket {bucket_name} for agent {agent_id}")
        return 0

    subscribers = config.get("subscribers", [])
    if not subscribers:
        logger.debug(f"Agent {agent_id} has no subscribers")
        return 0

    async with async_session_maker() as db:
        history_repo = VideoSendHistoryRepository(db)
        schedule_repo = ScheduledMessageRepository(db)
        contact_repo = ContactRepository(db)

        for subscriber_id in subscribers:
            try:
                subscriber_uuid = UUID(subscriber_id) if isinstance(subscriber_id, str) else subscriber_id

                # Verify contact exists
                contact = await contact_repo.get(subscriber_uuid)
                if not contact:
                    logger.warning(f"Subscriber {subscriber_id} not found, skipping")
                    continue

                # Get sent history for this contact
                sent_videos = await history_repo.get_sent_videos_for_contact(
                    agent_id, subscriber_uuid
                )

                # Select video
                selected_video, should_reset = agent.select_video_for_contact(
                    all_videos, sent_videos
                )

                if not selected_video:
                    logger.warning(f"No video selected for subscriber {subscriber_id}")
                    continue

                # Generate presigned URL (1 hour expiry)
                try:
                    video_url = minio_client.get_presigned_url(bucket_name, selected_video)
                except Exception as e:
                    logger.error(f"Error generating presigned URL for {selected_video}: {e}")
                    continue

                # Format caption
                caption = agent.format_caption(selected_video)

                # Create scheduled message for immediate delivery
                now = datetime.now(timezone.utc)
                await schedule_repo.create(
                    device_id=device_id,
                    contact_id=subscriber_uuid,
                    scheduled_at=now,
                    content_type="video",
                    content=caption,
                    media_url=video_url,
                    is_recurring=False,
                )

                # Record in history
                if should_reset:
                    await history_repo.reset_history_for_contact(agent_id, subscriber_uuid)

                await history_repo.record_video_sent(
                    agent_id, subscriber_uuid, selected_video
                )

                scheduled_count += 1
                logger.info(
                    f"Scheduled video '{selected_video}' for subscriber {subscriber_id}"
                )

            except Exception as e:
                logger.error(f"Error processing subscriber {subscriber_id}: {e}")
                continue

    return scheduled_count


async def process_due_jobs() -> int:
    """Process all due video distribution jobs.

    Returns:
        Total number of videos scheduled.
    """
    total_scheduled = 0

    async with async_session_maker() as db:
        job_repo = VideoDistributionJobRepository(db)
        agent_repo = AgentRepository(db)

        # Get due jobs
        due_jobs = await job_repo.get_due_jobs(limit=50)

        if not due_jobs:
            return 0

        logger.info(f"Found {len(due_jobs)} due video distribution jobs")

        for job in due_jobs:
            try:
                # Get the agent
                agent = await agent_repo.get(job.agent_id)
                if not agent:
                    logger.warning(f"Agent {job.agent_id} not found for job {job.id}")
                    continue

                # Skip inactive agents
                if not agent.is_active:
                    logger.debug(f"Agent {job.agent_id} is inactive, skipping")
                    continue

                # Verify it's a video_distributor agent
                if agent.agent_type != "video_distributor":
                    logger.warning(
                        f"Agent {job.agent_id} is not a video_distributor, skipping"
                    )
                    continue

                # Process the distribution
                scheduled = await process_distribution_job(
                    agent.id,
                    agent.device_id,
                    agent.config,
                )
                total_scheduled += scheduled

                # Update job timestamps
                now = datetime.now(timezone.utc)
                video_agent = VideoDistributorAgent(agent.config)
                next_run = video_agent.calculate_next_run(now)

                await job_repo.update_run_times(job, last_run=now, next_run=next_run)

                logger.info(
                    f"Processed job {job.id}: scheduled {scheduled} videos, "
                    f"next run at {next_run.isoformat()}"
                )

            except Exception as e:
                logger.error(f"Error processing job {job.id}: {e}")
                continue

    return total_scheduled


async def main() -> None:
    """Main video distributor worker loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting video distributor worker...")
    logger.info(f"Checking for due jobs every {CHECK_INTERVAL_SECONDS} seconds")

    while True:
        try:
            scheduled_count = await process_due_jobs()
            if scheduled_count > 0:
                logger.info(f"Scheduled {scheduled_count} videos for distribution")
        except Exception as e:
            logger.error(f"Error in video distributor loop: {e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
