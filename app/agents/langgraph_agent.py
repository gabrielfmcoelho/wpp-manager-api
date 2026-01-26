"""LangGraph-based agent for complex conversational flows."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.agents.base import AgentResponse, BaseAgent
from app.config import settings
from app.models import Conversation

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class LangGraphAgent(BaseAgent):
    """Agent using LangGraph for complex multi-step conversations.

    Config structure:
    {
        "model": "gpt-4o-mini",  # LLM model to use
        "temperature": 0.7,
        "system_prompt": "You are a helpful assistant...",
        "max_tokens": 500,
        "tools": [],  # Optional list of tool definitions
        "ignore_groups": true,
        "trigger_keywords": ["help", "support"],  # Optional keywords to trigger agent
        "conversation_timeout_minutes": 30  # Reset conversation after inactivity
    }
    """

    def __init__(self, config: dict[str, Any], llm_service: LLMService | None = None):
        super().__init__(config)
        self.llm_service = llm_service
        self.model = config.get("model", "gpt-4o-mini")
        self.temperature = config.get("temperature", 0.7)
        self.system_prompt = config.get(
            "system_prompt",
            "You are a helpful assistant. Be concise and friendly.",
        )
        self.max_tokens = config.get("max_tokens", 500)
        self.ignore_groups = config.get("ignore_groups", True)
        self.trigger_keywords = config.get("trigger_keywords", [])
        self._llm = None
        self._graph = None

    def _get_llm(self):
        """Lazy load the LLM."""
        if self._llm is None:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not configured")

            try:
                from langchain_openai import ChatOpenAI

                self._llm = ChatOpenAI(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    api_key=settings.OPENAI_API_KEY,
                )
            except ImportError:
                raise ImportError(
                    "langchain-openai is required for LangGraph agents. "
                    "Install with: pip install langchain-openai langgraph"
                )

        return self._llm

    def _build_graph(self):
        """Build the LangGraph conversation graph."""
        if self._graph is not None:
            return self._graph

        try:
            from typing import Annotated, TypedDict

            from langgraph.graph import StateGraph
            from langgraph.graph.message import add_messages

            class State(TypedDict):
                messages: Annotated[list, add_messages]

            llm = self._get_llm()

            def chatbot(state: State) -> dict:
                """Process messages with the LLM."""
                return {"messages": [llm.invoke(state["messages"])]}

            graph_builder = StateGraph(State)
            graph_builder.add_node("chatbot", chatbot)
            graph_builder.set_entry_point("chatbot")
            graph_builder.set_finish_point("chatbot")

            self._graph = graph_builder.compile()
            return self._graph

        except ImportError:
            raise ImportError(
                "langgraph is required for LangGraph agents. "
                "Install with: pip install langgraph langchain-openai"
            )

    async def can_handle(self, message: dict[str, Any]) -> bool:
        """Check if this agent should handle the message."""
        # Skip group messages if configured
        if self.ignore_groups and message.get("isGroup", False):
            return False

        # Only handle text messages
        if message.get("type", "text") != "text":
            return False

        text = message.get("body", "")
        if not text:
            return False

        # If trigger keywords are set, only handle matching messages
        if self.trigger_keywords:
            text_lower = text.lower()
            return any(kw.lower() in text_lower for kw in self.trigger_keywords)

        return True

    async def process(
        self,
        message: dict[str, Any],
        state: dict | None = None,
        conversation: Conversation | None = None,
    ) -> AgentResponse:
        """Process message with LangGraph or LLMService.

        If LLMService is provided, uses it directly for simpler responses.
        Otherwise falls back to LangGraph for complex flows.

        Returns tuple of (response, None, False) for backward compatibility.
        """
        if not await self.can_handle(message):
            return (None, None, False)

        text = message.get("body", "")
        push_name = message.get("pushName", "User")

        # If LLMService is available, use it for simple responses
        if self.llm_service is not None:
            try:
                response = await self.llm_service.generate_response(
                    system_prompt=self.system_prompt,
                    user_message=f"[{push_name}]: {text}",
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                return (response, None, False)
            except Exception as e:
                logger.error(f"Error using LLMService: {e}")
                return (None, None, False)

        # Fallback to LangGraph for complex flows
        try:
            graph = self._build_graph()

            # Build messages with system prompt and user message
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"[{push_name}]: {text}"),
            ]

            # Run the graph
            result = await graph.ainvoke({"messages": messages})

            # Extract response from result
            if result and "messages" in result:
                last_message = result["messages"][-1]
                if hasattr(last_message, "content"):
                    return (last_message.content, None, False)

            return (None, None, False)

        except ImportError as e:
            logger.error(f"LangGraph dependencies not installed: {e}")
            return (None, None, False)
        except Exception as e:
            logger.error(f"Error in LangGraph agent: {e}")
            return (None, None, False)
