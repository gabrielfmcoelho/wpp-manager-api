"""Contact management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAuthContext, DbSession
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.repositories import ContactRepository
from app.schemas import ContactCreate, ContactDetail, ContactList, ContactUpdate

router = APIRouter(prefix="/contacts", tags=["contacts"])


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


@router.get("", response_model=ContactList)
async def list_contacts(
    db: DbSession,
    auth: CurrentAuthContext,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    device_id: UUID | None = Query(None, description="Filter by device ID"),
    search: str | None = None,
    is_blocked: bool | None = None,
    is_group: bool | None = None,
):
    """List contacts for authenticated user's devices."""
    # User has no devices - return empty list
    if not auth.device_ids:
        return ContactList(items=[], total=0, skip=skip, limit=limit)

    # Validate device access if specific device requested
    if device_id:
        if not auth.has_device_access(device_id):
            raise ForbiddenError("You do not have access to this device")

    repo = ContactRepository(db)
    items, total = await repo.list(
        device_id=device_id,  # None means all devices
        device_ids=auth.device_ids if not device_id else None,  # Pass all accessible devices if no filter
        skip=skip,
        limit=limit,
        search=search,
        is_blocked=is_blocked,
        is_group=is_group,
    )
    return ContactList(items=items, total=total, skip=skip, limit=limit)


@router.post("", response_model=ContactDetail, status_code=201)
async def create_contact(
    data: ContactCreate,
    db: DbSession,
    auth: CurrentAuthContext,
    device_id: UUID | None = Query(None, description="Device to create contact for"),
):
    """Create a new contact."""
    target_device_id = _get_device_id(auth, device_id)

    repo = ContactRepository(db)

    # Generate JID from phone number
    clean_number = "".join(filter(str.isdigit, data.phone_number))
    whatsapp_jid = f"{clean_number}@s.whatsapp.net"

    contact = await repo.create(
        device_id=target_device_id,
        phone_number=data.phone_number,
        whatsapp_jid=whatsapp_jid,
        name=data.name,
        description=data.description,
    )
    return contact


@router.get("/{contact_id}", response_model=ContactDetail)
async def get_contact(
    contact_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Get contact details."""
    repo = ContactRepository(db)

    # Try to find contact in any of user's accessible devices
    for device_id in auth.device_ids:
        contact = await repo.get_by_device(device_id, contact_id)
        if contact:
            return contact

    raise NotFoundError("Contact", str(contact_id))


@router.patch("/{contact_id}", response_model=ContactDetail)
async def update_contact(
    contact_id: UUID,
    data: ContactUpdate,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Update contact details."""
    repo = ContactRepository(db)

    # Find contact and verify access
    contact = None
    for device_id in auth.device_ids:
        contact = await repo.get_by_device(device_id, contact_id)
        if contact:
            break

    if not contact:
        raise NotFoundError("Contact", str(contact_id))

    update_data = data.model_dump(exclude_unset=True)
    contact = await repo.update(contact, **update_data)
    return contact


@router.post("/{contact_id}/block", response_model=ContactDetail)
async def block_contact(
    contact_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Block a contact."""
    repo = ContactRepository(db)

    # Find contact and verify access
    contact = None
    for device_id in auth.device_ids:
        contact = await repo.get_by_device(device_id, contact_id)
        if contact:
            break

    if not contact:
        raise NotFoundError("Contact", str(contact_id))

    contact = await repo.update(contact, is_blocked=True)
    return contact


@router.delete("/{contact_id}/block", response_model=ContactDetail)
async def unblock_contact(
    contact_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Unblock a contact."""
    repo = ContactRepository(db)

    # Find contact and verify access
    contact = None
    for device_id in auth.device_ids:
        contact = await repo.get_by_device(device_id, contact_id)
        if contact:
            break

    if not contact:
        raise NotFoundError("Contact", str(contact_id))

    contact = await repo.update(contact, is_blocked=False)
    return contact
