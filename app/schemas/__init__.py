"""Pydantic schemas for request/response models."""

from app.schemas.agent import (
    AgentCreate,
    AgentDetail,
    AgentList,
    AgentUpdate,
)
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyDetail,
    ApiKeyList,
    ApiKeyResponse,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.contact import (
    ContactCreate,
    ContactDetail,
    ContactList,
    ContactUpdate,
)
from app.schemas.device import (
    DeviceCreate,
    DeviceDetail,
    DeviceList,
    DeviceStatus,
    DeviceUpdate,
)
from app.schemas.ignore_rule import (
    IgnoreRuleCreate,
    IgnoreRuleDetail,
    IgnoreRuleList,
)
from app.schemas.message import (
    MessageCreate,
    MessageDetail,
    MessageList,
    WebhookPayload,
)
from app.schemas.scheduled_message import (
    ScheduledMessageCreate,
    ScheduledMessageDetail,
    ScheduledMessageList,
    ScheduledMessageUpdate,
)
from app.schemas.user import (
    UserDetail,
    UserDeviceAssign,
    UserDeviceList,
    UserDeviceResponse,
)

__all__ = [
    # Common
    "PaginatedResponse",
    "PaginationParams",
    # Device
    "DeviceCreate",
    "DeviceDetail",
    "DeviceList",
    "DeviceStatus",
    "DeviceUpdate",
    # Contact
    "ContactCreate",
    "ContactDetail",
    "ContactList",
    "ContactUpdate",
    # Message
    "MessageCreate",
    "MessageDetail",
    "MessageList",
    "WebhookPayload",
    # Scheduled Message
    "ScheduledMessageCreate",
    "ScheduledMessageDetail",
    "ScheduledMessageList",
    "ScheduledMessageUpdate",
    # Agent
    "AgentCreate",
    "AgentDetail",
    "AgentList",
    "AgentUpdate",
    # Ignore Rule
    "IgnoreRuleCreate",
    "IgnoreRuleDetail",
    "IgnoreRuleList",
    # API Key
    "ApiKeyCreate",
    "ApiKeyDetail",
    "ApiKeyList",
    "ApiKeyResponse",
    # User
    "UserDetail",
    "UserDeviceAssign",
    "UserDeviceList",
    "UserDeviceResponse",
]
