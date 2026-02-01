"""Video distributor agent for sending videos from MinIO to subscribers."""

import logging
import random
from datetime import datetime, time, timedelta, timezone
from typing import Any

from app.agents.base import AgentResponse, BaseAgent
from app.models import Conversation

logger = logging.getLogger(__name__)


class VideoDistributorAgent(BaseAgent):
    """Agent that distributes videos from a MinIO bucket to subscribers.

    This agent does NOT handle incoming messages directly. Instead, it is
    processed by the video_distributor_worker which runs periodically to:
    1. Check if it's time to distribute videos
    2. Select random unseen videos for each subscriber
    3. Create ScheduledMessages for immediate delivery

    Config structure:
    {
        "bucket_name": "my-videos",
        "interval_hours": 24,
        "subscribers": ["contact-uuid-1", "contact-uuid-2"],
        "caption_template": "Check out this video! {{video_name}}",
        "active_hours_start": "09:00",  # Optional
        "active_hours_end": "18:00",    # Optional
    }
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.bucket_name = config.get("bucket_name", "")
        self.interval_hours = config.get("interval_hours", 24)
        self.subscribers = config.get("subscribers", [])
        self.caption_template = config.get(
            "caption_template",
            "Check out this video!",
        )
        self.active_hours_start = config.get("active_hours_start")
        self.active_hours_end = config.get("active_hours_end")

    async def can_handle(self, message: dict[str, Any]) -> bool:
        """Video distributor does not handle incoming messages.

        Distribution is handled by the video_distributor_worker.
        """
        return False

    async def process(
        self,
        message: dict[str, Any],
        state: dict | None = None,
        conversation: Conversation | None = None,
    ) -> AgentResponse:
        """Video distributor does not process incoming messages.

        Distribution is handled by the video_distributor_worker.

        Returns:
            Always returns (None, None, False) to indicate no response.
        """
        return (None, None, False)

    def is_within_active_hours(self, check_time: datetime | None = None) -> bool:
        """Check if the current time is within active hours.

        If no active hours are configured, always returns True.

        Args:
            check_time: Time to check (default: now in UTC).

        Returns:
            True if within active hours or no hours configured.
        """
        if not self.active_hours_start or not self.active_hours_end:
            return True

        if check_time is None:
            check_time = datetime.now(timezone.utc)

        try:
            start_parts = self.active_hours_start.split(":")
            end_parts = self.active_hours_end.split(":")

            start_time = time(int(start_parts[0]), int(start_parts[1]))
            end_time = time(int(end_parts[0]), int(end_parts[1]))
            current_time = check_time.time()

            # Handle case where end time is before start time (spans midnight)
            if end_time < start_time:
                return current_time >= start_time or current_time <= end_time
            else:
                return start_time <= current_time <= end_time

        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid active hours format: {e}")
            return True

    def select_video_for_contact(
        self,
        all_videos: list[str],
        sent_videos: list[str],
    ) -> tuple[str | None, bool]:
        """Select a random video that hasn't been sent to this contact.

        Args:
            all_videos: List of all available video filenames.
            sent_videos: List of video filenames already sent to this contact.

        Returns:
            Tuple of (selected_video, should_reset_history).
            If all videos have been sent, returns (random_video, True) to
            indicate history should be reset after sending.
        """
        if not all_videos:
            return (None, False)

        # Find videos not yet sent
        available = [v for v in all_videos if v not in sent_videos]

        # If all videos have been sent, reset and pick from all
        should_reset = False
        if not available:
            available = all_videos
            should_reset = True

        # Select random video
        selected = random.choice(available)
        return (selected, should_reset)

    def format_caption(self, video_filename: str) -> str:
        """Format the caption template with video information.

        Supported placeholders:
        - {{video_name}}: The video filename without extension
        - {{video_filename}}: The full video filename

        Args:
            video_filename: The video filename.

        Returns:
            Formatted caption string.
        """
        # Remove extension for video_name
        video_name = video_filename.rsplit(".", 1)[0] if "." in video_filename else video_filename

        caption = self.caption_template
        caption = caption.replace("{{video_name}}", video_name)
        caption = caption.replace("{{video_filename}}", video_filename)

        return caption

    def calculate_next_run(self, from_time: datetime | None = None) -> datetime:
        """Calculate when the next distribution should run.

        Args:
            from_time: Base time to calculate from (default: now).

        Returns:
            DateTime for next scheduled run.
        """
        if from_time is None:
            from_time = datetime.now(timezone.utc)

        next_run = from_time + timedelta(hours=self.interval_hours)

        # If active hours are configured, adjust to start within active window
        if self.active_hours_start and self.active_hours_end:
            try:
                start_parts = self.active_hours_start.split(":")
                start_hour = int(start_parts[0])
                start_minute = int(start_parts[1])

                # If next_run is outside active hours, move to next active start
                if not self.is_within_active_hours(next_run):
                    # Move to next day's active start time
                    next_run = next_run.replace(
                        hour=start_hour,
                        minute=start_minute,
                        second=0,
                        microsecond=0,
                    )
                    # If we're already past today's start time, move to tomorrow
                    if next_run <= from_time:
                        next_run += timedelta(days=1)

            except (ValueError, IndexError):
                pass  # Keep original next_run if parsing fails

        return next_run
