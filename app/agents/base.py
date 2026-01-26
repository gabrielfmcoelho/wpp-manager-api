"""Base agent interface."""

from abc import ABC, abstractmethod
from typing import Any

from app.models import Conversation

# Type alias for stateful agent response
AgentResponse = tuple[str | None, dict | None, bool]
"""Return type for stateful agent processing.

Tuple of (response, new_state, is_conversation_closed):
- response: The text response to send, or None to not respond
- new_state: Updated agent state dict to persist, or None for no state change
- is_conversation_closed: True to close the conversation and stop future responses
"""


class BaseAgent(ABC):
    """Abstract base class for message handling agents."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the agent with configuration.

        Args:
            config: Agent-specific configuration from the database.
        """
        self.config = config

    @abstractmethod
    async def process(
        self,
        message: dict[str, Any],
        state: dict | None = None,
        conversation: Conversation | None = None,
    ) -> AgentResponse:
        """Process an incoming message and return a response with state.

        Args:
            message: The incoming message data containing:
                - from: Sender's WhatsApp JID
                - body: Message text content
                - type: Message type (text, image, etc.)
                - hasMedia: Whether the message has media
                - isGroup: Whether from a group chat
                - pushName: Sender's push name
                - contact_id: The contact's UUID
                - Additional fields depending on message type
            state: The current agent state from the conversation, or None
            conversation: The conversation object, or None if no active conversation

        Returns:
            A tuple of (response, new_state, is_conversation_closed):
            - response: Text to send back, or None to not respond
            - new_state: Updated state dict to persist, or None for no change
            - is_conversation_closed: True to close the conversation
        """
        pass

    @abstractmethod
    async def can_handle(self, message: dict[str, Any]) -> bool:
        """Check if this agent can handle the given message.

        This is a quick check to avoid unnecessary processing.
        Agents are still allowed to return None from process()
        even if can_handle() returns True.

        Args:
            message: The incoming message data.

        Returns:
            True if this agent might handle the message.
        """
        pass
