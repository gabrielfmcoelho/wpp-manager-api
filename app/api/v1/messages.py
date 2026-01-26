"""Message endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAuthContext, DbSession
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.repositories import MessageRepository
from app.models.message import MessageDirection, MessageStatus
from app.schemas import MessageCreate, MessageDetail, MessageList
from app.services import MessageService

router = APIRouter(prefix="/messages", tags=["messages"])


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


def _get_device_id_optional(auth: CurrentAuthContext, device_id: UUID | None) -> UUID | None:
    """Get the device ID to use, returning None if user has no devices."""
    if device_id:
        if not auth.has_device_access(device_id):
            raise ForbiddenError("You do not have access to this device")
        return device_id

    # Use first available device if not specified
    if auth.device_ids:
        return auth.device_ids[0]

    # No devices available - return None for list operations
    return None


@router.get("", response_model=MessageList)
async def list_messages(
    db: DbSession,
    auth: CurrentAuthContext,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    device_id: UUID | None = Query(None, description="Filter by device ID"),
    contact_id: UUID | None = None,
    direction: MessageDirection | None = None,
    status: MessageStatus | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
):
    """List messages for authenticated user's devices."""
    target_device_id = _get_device_id_optional(auth, device_id)

    # User has no devices - return empty list
    if target_device_id is None:
        return MessageList(items=[], total=0, skip=skip, limit=limit)

    repo = MessageRepository(db)
    items, total = await repo.list(
        device_id=target_device_id,
        skip=skip,
        limit=limit,
        contact_id=contact_id,
        direction=direction,
        status=status,
        after=after,
        before=before,
    )
    return MessageList(items=items, total=total, skip=skip, limit=limit)


@router.post("", status_code=201)
async def send_message(
    data: MessageCreate,
    db: DbSession,
    auth: CurrentAuthContext,
    device_id: UUID | None = Query(None, description="Device to send message from"),
):
    """Send a message to a phone number."""
    target_device_id = _get_device_id(auth, device_id)

    service = MessageService(db, target_device_id)
    result = await service.send_message(
        phone=data.phone,
        content=data.content,
        content_type=data.content_type,
        media_url=data.media_url,
    )
    return result


@router.get("/{message_id}", response_model=MessageDetail)
async def get_message(
    message_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Get message details."""
    repo = MessageRepository(db)

    # Try to find message in any of user's accessible devices
    for device_id in auth.device_ids:
        message = await repo.get_by_device(device_id, message_id)
        if message:
            return message

    raise NotFoundError("Message", str(message_id))
