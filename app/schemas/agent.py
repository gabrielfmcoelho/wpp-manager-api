"""Agent schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    """Base agent schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    agent_type: str = Field(..., description="Agent type: 'langgraph' or 'rule_based'")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="""Agent configuration. Common fields:
        - rules: Array of {pattern, response} for rule_based agents
        - model: LLM model name for langgraph agents
        - temperature: LLM temperature for langgraph agents
        - system_prompt: System prompt for langgraph agents
        - trigger_keywords: Keywords that trigger the agent
        - allowed_contacts: Array of contact UUIDs. If set, agent only responds to these contacts. Empty = all contacts.
        - ignore_groups: Boolean. If true, agent ignores group messages.""",
    )
    priority: int = Field(default=0, description="Higher priority agents run first")


class AgentCreate(AgentBase):
    """Schema for creating a new agent."""

    pass


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None
    priority: int | None = None


class AgentDetail(BaseModel):
    """Schema for agent details."""

    id: UUID
    device_id: UUID
    name: str
    description: str | None
    agent_type: str
    config: dict[str, Any]
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentList(BaseModel):
    """Schema for paginated agent list."""

    items: list[AgentDetail]
    total: int
    skip: int
    limit: int
