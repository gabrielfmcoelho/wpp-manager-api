"""Agent runner service for orchestrating message processing agents."""

import logging
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
from app.services.llm_service import LLMService

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
) -> int:
    """Create scheduled messages for a subscription.

    Args:
        schedule_repo: The scheduled message repository
        device_id: The device ID
        contact_id: The contact ID
        config: Schedule configuration with days, time, and template

    Returns:
        Number of schedules created
    """
    days = config.get("days", 30)
    time_str = config.get("time", "09:00")
    template = config.get("template", "Good morning! Here's your daily update...")

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

    created_count = 0
    for day_offset in range(days):
        scheduled_at = base_date + timedelta(days=day_offset)

        await schedule_repo.create(
            device_id=device_id,
            contact_id=contact_id,
            scheduled_at=scheduled_at,
            content_type="text",
            content=template,
            is_recurring=False,
        )
        created_count += 1

    logger.info(
        f"Created {created_count} scheduled messages for contact {contact_id} "
        f"starting at {base_date}"
    )
    return created_count
