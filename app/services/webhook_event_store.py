"""Webhook event store for debugging - stores events in Redis with auto-expiration."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from redis.asyncio import Redis


class WebhookEventStore:
    """Store webhook events in Redis for debugging."""

    EVENTS_KEY = "webhook_events"
    MAX_EVENTS = 500  # Keep last 500 events
    EVENT_TTL = 86400  # 24 hours

    def __init__(self, redis: Redis):
        self.redis = redis

    async def store_event(
        self,
        device_id: str,
        event_type: str,
        payload: dict,
        status: str = "received",
        error: str | None = None,
    ) -> str:
        """Store a webhook event, return event ID."""
        event_id = str(uuid4())
        event = {
            "id": event_id,
            "device_id": device_id,
            "event_type": event_type,
            "payload": payload,
            "status": status,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Store as JSON in Redis list
        await self.redis.lpush(self.EVENTS_KEY, json.dumps(event))
        # Trim to max events
        await self.redis.ltrim(self.EVENTS_KEY, 0, self.MAX_EVENTS - 1)
        # Set TTL on key
        await self.redis.expire(self.EVENTS_KEY, self.EVENT_TTL)

        return event_id

    async def update_status(
        self, event_id: str, status: str, error: str | None = None
    ) -> None:
        """Update event status (processed, failed, ignored)."""
        # Read all events, update matching one, write back
        raw_events = await self.redis.lrange(self.EVENTS_KEY, 0, -1)
        for i, raw_event in enumerate(raw_events):
            event = json.loads(raw_event)
            if event["id"] == event_id:
                event["status"] = status
                event["error"] = error
                await self.redis.lset(self.EVENTS_KEY, i, json.dumps(event))
                break

    async def get_events(
        self,
        limit: int = 50,
        offset: int = 0,
        device_id: str | None = None,
        event_type: str | None = None,
    ) -> list[dict]:
        """Get recent events with optional filtering."""
        raw_events = await self.redis.lrange(self.EVENTS_KEY, 0, -1)
        events = [json.loads(e) for e in raw_events]

        # Filter
        if device_id:
            events = [e for e in events if e["device_id"] == device_id]
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]

        # Paginate
        return events[offset : offset + limit]

    async def get_event(self, event_id: str) -> dict | None:
        """Get single event by ID."""
        raw_events = await self.redis.lrange(self.EVENTS_KEY, 0, -1)
        for raw_event in raw_events:
            event = json.loads(raw_event)
            if event["id"] == event_id:
                return event
        return None

    async def get_total_count(
        self, device_id: str | None = None, event_type: str | None = None
    ) -> int:
        """Get total count of events with optional filtering."""
        raw_events = await self.redis.lrange(self.EVENTS_KEY, 0, -1)
        events = [json.loads(e) for e in raw_events]

        # Filter
        if device_id:
            events = [e for e in events if e["device_id"] == device_id]
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]

        return len(events)

    async def clear_events(self) -> None:
        """Clear all stored events."""
        await self.redis.delete(self.EVENTS_KEY)
