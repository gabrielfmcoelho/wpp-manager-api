"""Scheduled message endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAuthContext, DbSession
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.db.repositories import ContactRepository, ScheduledMessageRepository
from app.schemas import (
    ScheduledMessageCreate,
    ScheduledMessageDetail,
    ScheduledMessageList,
    ScheduledMessageUpdate,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _get_device_id(auth: CurrentAuthContext, device_id: UUID | None) -> UUID:
    """Get the device ID to use, validating access."""
    if device_id:
        if not auth.has_device_access(device_id):
            raise ForbiddenError("You do not have access to this device")
        return device_id

    # Use first available device if not specified
    if auth.device_ids:
        return auth.device_ids[0]

    raise ForbiddenError("No device access available")


@router.get("", response_model=ScheduledMessageList)
async def list_scheduled_messages(
    db: DbSession,
    auth: CurrentAuthContext,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    device_id: UUID | None = Query(None, description="Filter by device ID"),
    contact_id: UUID | None = None,
    is_cancelled: bool | None = None,
    pending_only: bool = False,
):
    """List scheduled messages for authenticated user's devices."""
    # User has no devices - return empty list
    if not auth.device_ids:
        return ScheduledMessageList(items=[], total=0, skip=skip, limit=limit)

    # Validate device access if specific device requested
    if device_id:
        if not auth.has_device_access(device_id):
            raise ForbiddenError("You do not have access to this device")

    repo = ScheduledMessageRepository(db)
    items, total = await repo.list(
        device_id=device_id,  # None means all devices
        device_ids=auth.device_ids if not device_id else None,  # Pass all accessible devices if no filter
        skip=skip,
        limit=limit,
        contact_id=contact_id,
        is_cancelled=is_cancelled,
        pending_only=pending_only,
    )
    return ScheduledMessageList(items=items, total=total, skip=skip, limit=limit)


@router.post("", response_model=ScheduledMessageDetail, status_code=201)
async def create_scheduled_message(
    data: ScheduledMessageCreate,
    db: DbSession,
    auth: CurrentAuthContext,
    device_id: UUID | None = Query(None, description="Device to schedule message for"),
):
    """Create a new scheduled message."""
    target_device_id = _get_device_id(auth, device_id)

    # Verify contact exists and belongs to device
    contact_repo = ContactRepository(db)
    contact = await contact_repo.get_by_device(target_device_id, data.contact_id)
    if not contact:
        raise NotFoundError("Contact", str(data.contact_id))

    # Validate recurring settings
    if data.is_recurring and not data.cron_expression:
        raise BadRequestError("cron_expression is required for recurring messages")

    repo = ScheduledMessageRepository(db)
    scheduled = await repo.create(
        device_id=target_device_id,
        contact_id=data.contact_id,
        scheduled_at=data.scheduled_at,
        content_type=data.content_type,
        content=data.content,
        media_url=data.media_url,
        is_recurring=data.is_recurring,
        cron_expression=data.cron_expression,
    )
    return scheduled


@router.get("/{schedule_id}", response_model=ScheduledMessageDetail)
async def get_scheduled_message(
    schedule_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Get scheduled message details."""
    repo = ScheduledMessageRepository(db)

    # Try to find in any of user's accessible devices
    for device_id in auth.device_ids:
        scheduled = await repo.get_by_device(device_id, schedule_id)
        if scheduled:
            return scheduled

    raise NotFoundError("Scheduled Message", str(schedule_id))


@router.patch("/{schedule_id}", response_model=ScheduledMessageDetail)
async def update_scheduled_message(
    schedule_id: UUID,
    data: ScheduledMessageUpdate,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Update a scheduled message."""
    repo = ScheduledMessageRepository(db)

    # Find scheduled message and verify access
    scheduled = None
    for device_id in auth.device_ids:
        scheduled = await repo.get_by_device(device_id, schedule_id)
        if scheduled:
            break

    if not scheduled:
        raise NotFoundError("Scheduled Message", str(schedule_id))

    # Cannot update if already sent
    if scheduled.sent_at:
        raise BadRequestError("Cannot update a message that has already been sent")

    update_data = data.model_dump(exclude_unset=True)
    scheduled = await repo.update(scheduled, **update_data)
    return scheduled


@router.delete("/{schedule_id}", status_code=204)
async def cancel_scheduled_message(
    schedule_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Cancel a scheduled message."""
    repo = ScheduledMessageRepository(db)

    # Find scheduled message and verify access
    scheduled = None
    for device_id in auth.device_ids:
        scheduled = await repo.get_by_device(device_id, schedule_id)
        if scheduled:
            break

    if not scheduled:
        raise NotFoundError("Scheduled Message", str(schedule_id))

    # Cannot cancel if already sent
    if scheduled.sent_at:
        raise BadRequestError("Cannot cancel a message that has already been sent")

    await repo.cancel(schedule_id)
