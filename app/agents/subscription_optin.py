"""Subscription opt-in agent for managing periodic message subscriptions."""

import logging
import re
from typing import Any

from app.agents.base import AgentResponse, BaseAgent
from app.models import Conversation

logger = logging.getLogger(__name__)


class SubscriptionOptinState:
    """State constants for the subscription opt-in flow."""

    INITIAL = "initial"
    AWAITING_RESPONSE = "awaiting_response"
    COMPLETED = "completed"


class SubscriptionOptinAgent(BaseAgent):
    """Agent that asks contacts if they want periodic messages.

    Flow:
    1. On first message from whitelisted contact → Send opt-in prompt
    2. If user replies YES → Create scheduled messages, close conversation
    3. If user replies NO → Close conversation
    4. On closed conversation → Ignore all messages

    Config structure:
    {
        "prompt_message": "Do you want to receive periodic messages? Reply YES or NO",
        "yes_confirmation": "Great! You'll receive daily updates for 30 days.",
        "no_confirmation": "No problem! You won't receive scheduled messages.",
        "invalid_response": "Please reply with YES or NO.",
        "schedule_days": 30,
        "schedule_time": "09:00",
        "scheduled_message_template": "Good morning! Here's your daily update...",
        "allowed_contacts": ["contact-uuid-1", "contact-uuid-2"],
        "ignore_groups": true,

        # NEW: MinIO bucket integration (like video_distributor)
        "scheduled_content_type": "video",  # text | image | video
        "media_bucket_name": "videos",      # MinIO bucket to pull random media from
        "caption_template": "Check out today's tip! {{media_name}}"  # Caption template
    }
    """

    # Patterns for YES/NO responses (multilingual support)
    YES_PATTERNS = [
        r"^(yes|y|sim|si|ja|oui|da)$",
        r"^(yep|yeah|yup|sure|ok|okay)$",
        r"^(quero|aceito|confirmo)$",
    ]

    NO_PATTERNS = [
        r"^(no|n|nao|não|nein|non|net)$",
        r"^(nope|nah|never)$",
        r"^(não quero|recusar|rejeitar)$",
    ]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.prompt_message = config.get(
            "prompt_message",
            "Do you want to receive periodic messages? Reply YES or NO",
        )
        self.yes_confirmation = config.get(
            "yes_confirmation",
            "Great! You'll receive daily updates for 30 days.",
        )
        self.no_confirmation = config.get(
            "no_confirmation",
            "No problem! You won't receive scheduled messages.",
        )
        self.invalid_response = config.get(
            "invalid_response",
            "Please reply with YES or NO.",
        )
        self.schedule_days = config.get("schedule_days", 30)
        self.schedule_time = config.get("schedule_time", "09:00")
        self.scheduled_message_template = config.get(
            "scheduled_message_template",
            "Good morning! Here's your daily update...",
        )
        self.ignore_groups = config.get("ignore_groups", True)

        # MinIO bucket integration for media (like video_distributor)
        self.scheduled_content_type = config.get("scheduled_content_type", "text")
        self.media_bucket_name = config.get("media_bucket_name")
        self.caption_template = config.get(
            "caption_template",
            "Check out today's content!",
        )

        # Compile patterns
        self._yes_compiled = [
            re.compile(p, re.IGNORECASE) for p in self.YES_PATTERNS
        ]
        self._no_compiled = [
            re.compile(p, re.IGNORECASE) for p in self.NO_PATTERNS
        ]

    async def can_handle(self, message: dict[str, Any]) -> bool:
        """Check if this agent should handle the message."""
        # Skip group messages if configured
        if self.ignore_groups and message.get("isGroup", False):
            return False

        # Only handle text messages
        if message.get("type", "text") != "text":
            return False

        return True

    async def process(
        self,
        message: dict[str, Any],
        state: dict | None = None,
        conversation: Conversation | None = None,
    ) -> AgentResponse:
        """Process message through the subscription opt-in state machine.

        Returns:
            Tuple of (response, new_state, is_conversation_closed)
        """
        if not await self.can_handle(message):
            return (None, None, False)

        # Get current state
        current_state = SubscriptionOptinState.INITIAL
        if state:
            current_state = state.get("state", SubscriptionOptinState.INITIAL)

        # Check if conversation is already closed
        if conversation and conversation.status == "closed":
            logger.debug("Conversation already closed, ignoring message")
            return (None, None, False)

        # Check if already completed (shouldn't happen if conversation is properly closed)
        if current_state == SubscriptionOptinState.COMPLETED:
            logger.debug("Agent already completed, ignoring message")
            return (None, None, False)

        # Process based on current state
        if current_state == SubscriptionOptinState.INITIAL:
            return self._handle_initial_state(message)

        elif current_state == SubscriptionOptinState.AWAITING_RESPONSE:
            return self._handle_awaiting_response(message)

        return (None, None, False)

    def _handle_initial_state(self, message: dict[str, Any]) -> AgentResponse:
        """Handle initial state - send opt-in prompt on any message."""
        logger.info("Sending opt-in prompt to contact")

        new_state = {
            "state": SubscriptionOptinState.AWAITING_RESPONSE,
        }

        return (self.prompt_message, new_state, False)

    def _handle_awaiting_response(self, message: dict[str, Any]) -> AgentResponse:
        """Handle awaiting response state - check for YES/NO."""
        text = message.get("body", "").strip()

        # Check for YES
        if self._is_yes_response(text):
            logger.info("Contact accepted subscription, will create schedules")
            new_state = {
                "state": SubscriptionOptinState.COMPLETED,
                "create_schedules": True,
                "schedule_config": {
                    "days": self.schedule_days,
                    "time": self.schedule_time,
                    "template": self.scheduled_message_template,
                    # MinIO media support
                    "content_type": self.scheduled_content_type,
                    "media_bucket_name": self.media_bucket_name,
                    "caption_template": self.caption_template,
                },
            }
            return (self.yes_confirmation, new_state, True)

        # Check for NO
        if self._is_no_response(text):
            logger.info("Contact declined subscription")
            new_state = {
                "state": SubscriptionOptinState.COMPLETED,
                "create_schedules": False,
            }
            return (self.no_confirmation, new_state, True)

        # Invalid response - ask again
        logger.debug(f"Invalid response: '{text}', asking again")
        return (self.invalid_response, None, False)

    def _is_yes_response(self, text: str) -> bool:
        """Check if text matches a YES pattern."""
        for pattern in self._yes_compiled:
            if pattern.match(text):
                return True
        return False

    def _is_no_response(self, text: str) -> bool:
        """Check if text matches a NO pattern."""
        for pattern in self._no_compiled:
            if pattern.match(text):
                return True
        return False
