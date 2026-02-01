"""Repository classes for database operations."""

from app.db.repositories.agent import AgentRepository
from app.db.repositories.api_key import ApiKeyRepository
from app.db.repositories.base import BaseRepository
from app.db.repositories.contact import ContactRepository
from app.db.repositories.conversation import ConversationRepository
from app.db.repositories.device import DeviceRepository
from app.db.repositories.global_settings import GlobalSettingsRepository
from app.db.repositories.ignore_rule import IgnoreRuleRepository
from app.db.repositories.message import MessageRepository
from app.db.repositories.scheduled_message import ScheduledMessageRepository
from app.db.repositories.user_device import UserDeviceRepository
from app.db.repositories.video_distribution_job import VideoDistributionJobRepository
from app.db.repositories.video_send_history import VideoSendHistoryRepository

__all__ = [
    "BaseRepository",
    "DeviceRepository",
    "ContactRepository",
    "ConversationRepository",
    "GlobalSettingsRepository",
    "MessageRepository",
    "ScheduledMessageRepository",
    "AgentRepository",
    "IgnoreRuleRepository",
    "ApiKeyRepository",
    "UserDeviceRepository",
    "VideoDistributionJobRepository",
    "VideoSendHistoryRepository",
]
