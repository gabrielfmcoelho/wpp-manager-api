"""Debug endpoints for viewing webhook events."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentAuthContext, RedisClient
from app.services.webhook_event_store import WebhookEventStore

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/webhooks")
async def list_webhook_events(
    redis: RedisClient,
    auth: CurrentAuthContext,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    device_id: str | None = None,
    event_type: str | None = None,
):
    """List recent webhook events for debugging."""
    store = WebhookEventStore(redis)
    events = await store.get_events(
        limit=limit,
        offset=skip,
        device_id=device_id,
        event_type=event_type,
    )
    total = await store.get_total_count(device_id=device_id, event_type=event_type)
    return {"items": events, "total": total, "skip": skip, "limit": limit}


@router.get("/webhooks/{event_id}")
async def get_webhook_event(
    event_id: str,
    redis: RedisClient,
    auth: CurrentAuthContext,
):
    """Get single webhook event details."""
    store = WebhookEventStore(redis)
    event = await store.get_event(event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    return event


@router.delete("/webhooks")
async def clear_webhook_events(
    redis: RedisClient,
    auth: CurrentAuthContext,
):
    """Clear all stored webhook events."""
    store = WebhookEventStore(redis)
    await store.clear_events()
    return {"status": "cleared"}
