"""Rule-based agent using keyword/pattern matching."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from app.agents.base import AgentResponse, BaseAgent
from app.models import Conversation

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class RuleBasedAgent(BaseAgent):
    """Agent that matches messages against keyword patterns and returns templated responses.

    Config structure:
    {
        "rules": [
            {
                "pattern": "hello|hi|hey",  # Regex pattern
                "response": "Hello! How can I help you?",
                "case_insensitive": true,  # Optional, default true
                "match_type": "contains",  # "contains", "exact", "starts_with", "ends_with"
                "use_llm": false,  # Optional, generate response via LLM
                "llm_prompt": "..."  # System prompt for LLM (used if use_llm is true)
            },
            {
                "pattern": "price|pricing|cost",
                "response": "Our pricing starts at $99/month. Would you like more details?",
                "variables": {  # Optional variable substitution
                    "name": "{{pushName}}"  # Uses message.pushName
                }
            }
        ],
        "default_response": null,  # Optional fallback response
        "ignore_groups": true  # Optional, ignore group messages
    }
    """

    def __init__(self, config: dict[str, Any], llm_service: LLMService | None = None):
        super().__init__(config)
        self.llm_service = llm_service
        self.rules = config.get("rules", [])
        self.default_response = config.get("default_response")
        self.ignore_groups = config.get("ignore_groups", True)

        # Pre-compile patterns
        self._compiled_rules = []
        for rule in self.rules:
            pattern = rule.get("pattern", "")
            flags = re.IGNORECASE if rule.get("case_insensitive", True) else 0

            try:
                compiled = re.compile(pattern, flags)
                self._compiled_rules.append((compiled, rule))
            except re.error:
                # Skip invalid patterns
                continue

    async def can_handle(self, message: dict[str, Any]) -> bool:
        """Check if message might match any rules."""
        # Skip group messages if configured
        if self.ignore_groups and message.get("isGroup", False):
            return False

        # Only handle text messages
        if message.get("type", "text") != "text":
            return False

        text = message.get("body", "")
        if not text:
            return False

        return True

    async def process(
        self,
        message: dict[str, Any],
        state: dict | None = None,
        conversation: Conversation | None = None,
    ) -> AgentResponse:
        """Process message against rules and return matching response.

        Returns tuple of (response, None, False) for backward compatibility.
        Rule-based agents are stateless.

        If a rule has use_llm=True and LLMService is available, the response
        will be generated dynamically using the configured llm_prompt.
        """
        if not await self.can_handle(message):
            return (None, None, False)

        text = message.get("body", "").strip()

        for compiled_pattern, rule in self._compiled_rules:
            match_type = rule.get("match_type", "contains")

            matched = False
            if match_type == "exact":
                matched = compiled_pattern.fullmatch(text) is not None
            elif match_type == "starts_with":
                matched = compiled_pattern.match(text) is not None
            elif match_type == "ends_with":
                matched = compiled_pattern.search(text + "$") is not None
            else:  # contains
                matched = compiled_pattern.search(text) is not None

            if matched:
                # Check if this rule uses LLM for dynamic response
                if rule.get("use_llm") and self.llm_service:
                    try:
                        llm_prompt = rule.get(
                            "llm_prompt",
                            "Respond helpfully to the user's message."
                        )
                        # Substitute variables in the prompt
                        llm_prompt = self._substitute_variables(llm_prompt, message)

                        response = await self.llm_service.generate_response(
                            system_prompt=llm_prompt,
                            user_message=text,
                        )
                        return (response, None, False)
                    except Exception as e:
                        logger.error(f"Error generating LLM response: {e}")
                        # Fall through to static response if LLM fails
                        response = rule.get("response", "")
                        if response:
                            return (self._substitute_variables(response, message), None, False)
                        return (None, None, False)
                else:
                    # Static response
                    response = rule.get("response", "")
                    return (self._substitute_variables(response, message), None, False)

        return (self.default_response, None, False)

    def _substitute_variables(self, response: str, message: dict[str, Any]) -> str:
        """Substitute template variables in response."""
        # Replace {{key}} with message data
        def replacer(match: re.Match) -> str:
            key = match.group(1)
            value = message.get(key, "")
            return str(value) if value else ""

        return re.sub(r"\{\{(\w+)\}\}", replacer, response)
