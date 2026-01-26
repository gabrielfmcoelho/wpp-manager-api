"""Schemas for global settings."""

from pydantic import BaseModel, Field


class OpenAISettingsUpdate(BaseModel):
    """Schema for updating OpenAI settings."""

    use_default: bool = Field(
        default=True,
        description="Use default OpenAI settings from environment variables",
    )
    api_key: str | None = Field(
        default=None,
        description="Custom OpenAI API key (only used if use_default is False)",
    )
    host_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL (supports custom endpoints like Azure)",
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="Default model to use for LLM requests",
    )


class OpenAISettingsResponse(BaseModel):
    """Schema for OpenAI settings response (hides actual API key)."""

    use_default: bool = Field(description="Whether using default settings")
    host_url: str = Field(description="OpenAI API base URL")
    model: str = Field(description="Default model")
    has_api_key: bool = Field(description="Whether a custom API key is configured")

    model_config = {"from_attributes": True}
