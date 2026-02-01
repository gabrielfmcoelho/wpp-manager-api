"""Agent runner service for orchestrating message processing agents."""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import LangGraphAgent, RuleBasedAgent
from app.agents.subscription_optin import SubscriptionOptinAgent
from app.db.repositories import (
    AgentRepository,
    IgnoreRuleRepository,
    ScheduledMessageRepository,
)
from app.db.repositories.conversation import ConversationRepository
from app.db.repositories.video_send_history import VideoSendHistoryRepository
from app.services.llm_service import LLMService
from app.services.minio_client import get_minio_client

logger = logging.getLogger(__name__)


async def run_agents(
    db: AsyncSession,
    device_id: UUID,
    message: dict[str, Any],
    contact_id: UUID | None = None,
) -> str | None:
    """Run active agents against an incoming message.

    Agents are processed in priority order (highest first).
    Stops and returns the first non-None response.

    Args:
        db: Database session
        device_id: The device that received the message
        message: The incoming message data
        contact_id: The contact's UUID for stateful agent tracking

    Returns:
        The agent's response string, or None if no agent handled the message.
    """
    # Check ignore rules first
    ignore_repo = IgnoreRuleRepository(db)
    if await ignore_repo.should_ignore(device_id, message):
        logger.debug(f"Message ignored by rules for device {device_id}")
        return None

    # Get active agents ordered by priority
    agent_repo = AgentRepository(db)
    agents = await agent_repo.get_active_for_device(device_id)

    if not agents:
        logger.debug(f"No active agents for device {device_id}")
        return None

    logger.info(f"Running {len(agents)} agents for device {device_id}")

    # Initialize conversation repository for stateful agents
    conversation_repo = ConversationRepository(db)
    schedule_repo = ScheduledMessageRepository(db)

    # Initialize LLM service for agents that need it
    llm_service = LLMService(db)

    # Load conversation if we have a contact_id
    conversation = None
    agent_state = None
    if contact_id:
        conversation = await conversation_repo.get_active_for_contact(
            device_id, contact_id
        )
        if conversation:
            agent_state = conversation.agent_state
            logger.debug(f"Loaded conversation state for contact {contact_id}")

    for agent_config in agents:
        try:
            # Check contact whitelist if configured
            allowed_contacts = agent_config.config.get("allowed_contacts", [])
            if allowed_contacts:
                msg_contact_id = contact_id or message.get("contact_id")
                if msg_contact_id and str(msg_contact_id) not in allowed_contacts:
                    logger.debug(
                        f"Agent '{agent_config.name}' skipped - contact {msg_contact_id} "
                        f"not in whitelist"
                    )
                    continue

            # Check if agent should ignore groups
            if agent_config.config.get("ignore_groups", False):
                if message.get("is_group", False) or message.get("isGroup", False):
                    logger.debug(
                        f"Agent '{agent_config.name}' skipped - ignoring groups"
                    )
                    continue

            # Instantiate the appropriate agent type
            if agent_config.agent_type == "rule_based":
                agent = RuleBasedAgent(agent_config.config, llm_service)
            elif agent_config.agent_type == "langgraph":
                agent = LangGraphAgent(agent_config.config, llm_service)
            elif agent_config.agent_type == "subscription_optin":
                agent = SubscriptionOptinAgent(agent_config.config)
            else:
                logger.warning(f"Unknown agent type: {agent_config.agent_type}")
                continue

            # Quick check if agent can handle this message
            if not await agent.can_handle(message):
                continue

            # Process the message with state
            response, new_state, is_closed = await agent.process(
                message, agent_state, conversation
            )

            # Handle stateful response
            if new_state is not None and contact_id:
                # Ensure conversation exists
                if not conversation:
                    conversation, _ = await conversation_repo.get_or_create_for_contact(
                        device_id, contact_id
                    )

                # Check if we need to create schedules
                if new_state.get("create_schedules"):
                    schedule_config = new_state.get("schedule_config", {})
                    await _create_subscription_schedules(
                        schedule_repo,
                        device_id,
                        contact_id,
                        schedule_config,
                        agent_id=agent_config.id,
                        db=db,
                    )
                    logger.info(
                        f"Created subscription schedules for contact {contact_id}"
                    )

                # Update conversation state
                await conversation_repo.update_agent_state(conversation.id, new_state)
                logger.debug(f"Updated agent state for conversation {conversation.id}")

            # Close conversation if requested
            if is_closed and conversation:
                await conversation_repo.close_conversation(conversation.id)
                logger.info(f"Closed conversation {conversation.id}")

            if response:
                logger.info(
                    f"Agent '{agent_config.name}' (priority={agent_config.priority}) "
                    f"generated response for device {device_id}"
                )
                return response

        except Exception as e:
            logger.error(
                f"Error running agent '{agent_config.name}' "
                f"(id={agent_config.id}): {e}"
            )
            continue

    logger.debug(f"No agent response for device {device_id}")
    return None


async def _create_subscription_schedules(
    schedule_repo: ScheduledMessageRepository,
    device_id: UUID,
    contact_id: UUID,
    config: dict[str, Any],
    agent_id: UUID | None = None,
    db: AsyncSession | None = None,
) -> int:
    """Create scheduled messages for a subscription.

    Args:
        schedule_repo: The scheduled message repository
        device_id: The device ID
        contact_id: The contact ID
        config: Schedule configuration with days, time, template, and media settings
        agent_id: Optional agent ID for media history tracking
        db: Optional database session for history tracking

    Returns:
        Number of schedules created
    """
    days = config.get("days", 30)
    time_str = config.get("time", "09:00")
    template = config.get("template", "Good morning! Here's your daily update...")

    # Media configuration (new)
    content_type = config.get("content_type", "text")
    media_bucket_name = config.get("media_bucket_name")
    caption_template = config.get("caption_template", "Check out today's content!")

    # Parse time
    try:
        hour, minute = map(int, time_str.split(":"))
    except (ValueError, AttributeError):
        hour, minute = 9, 0

    # Create schedules starting tomorrow
    now = datetime.now(timezone.utc)
    base_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # If today's scheduled time has passed, start from tomorrow
    if base_date <= now:
        base_date += timedelta(days=1)

    # Get media files from MinIO if media bucket is configured
    all_media_files: list[str] = []
    minio_client = None
    history_repo = None

    if media_bucket_name and content_type != "text":
        try:
            minio_client = get_minio_client()
            all_media_files = minio_client.get_video_filenames(media_bucket_name)
            logger.info(
                f"Found {len(all_media_files)} media files in bucket {media_bucket_name}"
            )

            # Initialize history repo if we have agent_id and db
            if agent_id and db:
                history_repo = VideoSendHistoryRepository(db)
        except Exception as e:
            logger.error(f"Error accessing MinIO bucket {media_bucket_name}: {e}")
            # Fall back to text-only mode
            content_type = "text"
            all_media_files = []

    created_count = 0
    for day_offset in range(days):
        scheduled_at = base_date + timedelta(days=day_offset)

        # Determine content and media URL for this schedule
        message_content = template
        media_url = None

        if all_media_files and minio_client and content_type != "text":
            # Select random media from bucket
            selected_media, should_reset = await _select_random_media(
                agent_id=agent_id,
                contact_id=contact_id,
                all_media=all_media_files,
                history_repo=history_repo,
            )

            if selected_media:
                # Generate presigned URL (24 hour expiry for scheduled messages)
                media_url = minio_client.get_presigned_url(
                    media_bucket_name,
                    selected_media,
                    expires=timedelta(hours=24 + day_offset * 24),
                )

                # Format caption with media name
                media_name = (
                    selected_media.rsplit(".", 1)[0]
                    if "." in selected_media
                    else selected_media
                )
                message_content = caption_template.replace("{{media_name}}", media_name)
                message_content = message_content.replace(
                    "{{media_filename}}", selected_media
                )

                # Record in history if available
                if history_repo and agent_id:
                    if should_reset:
                        await history_repo.reset_history_for_contact(agent_id, contact_id)
                    await history_repo.record_video_sent(
                        agent_id, contact_id, selected_media
                    )

        await schedule_repo.create(
            device_id=device_id,
            contact_id=contact_id,
            scheduled_at=scheduled_at,
            content_type=content_type if media_url else "text",
            content=message_content,
            media_url=media_url,
            is_recurring=False,
        )
        created_count += 1

    logger.info(
        f"Created {created_count} scheduled messages for contact {contact_id} "
        f"starting at {base_date} (content_type={content_type})"
    )
    return created_count


async def _select_random_media(
    agent_id: UUID | None,
    contact_id: UUID,
    all_media: list[str],
    history_repo: VideoSendHistoryRepository | None,
) -> tuple[str | None, bool]:
    """Select a random media file that hasn't been sent to this contact.

    Args:
        agent_id: The agent's UUID for history tracking
        contact_id: The contact's UUID
        all_media: List of all available media filenames
        history_repo: Optional history repository for tracking

    Returns:
        Tuple of (selected_media, should_reset_history)
    """
    if not all_media:
        return (None, False)

    # Get sent media from history if available
    sent_media: list[str] = []
    if history_repo and agent_id:
        try:
            sent_media = await history_repo.get_sent_videos_for_contact(
                agent_id, contact_id
            )
        except Exception as e:
            logger.warning(f"Error getting media history: {e}")

    # Find media not yet sent
    available = [m for m in all_media if m not in sent_media]

    # If all media have been sent, reset and pick from all
    should_reset = False
    if not available:
        available = all_media
        should_reset = True

    # Select random media
    selected = random.choice(available)
    return (selected, should_reset)
