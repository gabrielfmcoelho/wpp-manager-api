"""Centralized LLM service for OpenAI integration."""

from dataclasses import dataclass

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories.global_settings import GlobalSettingsRepository


@dataclass
class OpenAIConfig:
    """Configuration for OpenAI client."""

    use_default: bool = True
    api_key: str | None = None
    host_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"


class LLMService:
    """
    Centralized LLM service for generating responses using OpenAI.

    Loads configuration from global settings or falls back to environment variables.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._config: OpenAIConfig | None = None
        self._client: AsyncOpenAI | None = None

    async def _load_config(self) -> OpenAIConfig:
        """Load OpenAI configuration from database."""
        if self._config is not None:
            return self._config

        repo = GlobalSettingsRepository(self.db)
        settings_record = await repo.get_by_key("openai")

        if settings_record and settings_record.value:
            value = settings_record.value
            self._config = OpenAIConfig(
                use_default=value.get("use_default", True),
                api_key=value.get("api_key"),
                host_url=value.get("host_url", "https://api.openai.com/v1"),
                model=value.get("model", "gpt-4o-mini"),
            )
        else:
            self._config = OpenAIConfig()

        return self._config

    async def get_client(self) -> AsyncOpenAI:
        """
        Get configured OpenAI client.

        If use_default is True, uses OPENAI_API_KEY from environment.
        Otherwise, uses custom api_key and host_url from settings.
        """
        if self._client is not None:
            return self._client

        config = await self._load_config()

        if config.use_default:
            # Use environment variable
            if not settings.OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY environment variable is not set. "
                    "Either set it or configure custom OpenAI settings."
                )
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            # Use custom settings
            if not config.api_key:
                raise ValueError(
                    "Custom OpenAI settings enabled but no API key configured. "
                    "Either provide an API key or use default settings."
                )
            self._client = AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.host_url,
            )

        return self._client

    async def get_model(self) -> str:
        """Get the configured default model."""
        config = await self._load_config()
        return config.model

    async def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        Generate a response using the OpenAI chat completion API.

        Args:
            system_prompt: System message to set the assistant's behavior
            user_message: User's input message
            model: Model to use (defaults to configured model)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response

        Returns:
            Generated response text
        """
        client = await self.get_client()
        config = await self._load_config()

        kwargs = {
            "model": model or config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
        }

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def generate_from_messages(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        Generate a response from a list of messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model to use (defaults to configured model)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response

        Returns:
            Generated response text
        """
        client = await self.get_client()
        config = await self._load_config()

        kwargs = {
            "model": model or config.model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""
