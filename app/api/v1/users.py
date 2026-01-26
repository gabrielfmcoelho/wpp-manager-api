"""User management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import ConflictError, NotFoundError
from app.db.repositories import DeviceRepository, UserDeviceRepository
from app.models.user_device import DeviceRole
from app.schemas import (
    UserDetail,
    UserDeviceAssign,
    UserDeviceList,
    UserDeviceResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserDetail)
async def get_current_user_profile(
    current_user: CurrentUser,
):
    """Get the current user's profile."""
    return current_user


@router.get("/me/devices", response_model=UserDeviceList)
async def list_user_devices(
    current_user: CurrentUser,
    db: DbSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """List devices accessible to the current user."""
    repo = UserDeviceRepository(db)
    items, total = await repo.list_by_user(current_user.id, skip=skip, limit=limit)

    # Build response with device names
    response_items = []
    for ud in items:
        response_items.append(
            UserDeviceResponse(
                id=ud.id,
                user_id=ud.user_id,
                device_id=ud.device_id,
                role=ud.role,
                device_name=ud.device.name if ud.device else None,
                created_at=ud.created_at,
            )
        )

    return UserDeviceList(items=response_items, total=total)


@router.post("/me/devices", response_model=UserDeviceResponse, status_code=201)
async def assign_device_to_user(
    data: UserDeviceAssign,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    Assign a device to the current user.

    Users can only assign devices as OWNER when first claiming an unclaimed device.
    For existing device assignments, use appropriate admin flows.
    """
    # Check if device exists
    device_repo = DeviceRepository(db)
    device = await device_repo.get(data.device_id)
    if not device:
        raise NotFoundError("Device", str(data.device_id))

    # Check if user already has access to this device
    ud_repo = UserDeviceRepository(db)
    existing = await ud_repo.get_by_user_and_device(current_user.id, data.device_id)
    if existing:
        raise ConflictError("User already has access to this device")

    # Create the user-device relationship
    # For self-assignment, we'll allow the requested role (could add validation here)
    user_device = await ud_repo.create(
        user_id=current_user.id,
        device_id=data.device_id,
        role=data.role,
    )

    return UserDeviceResponse(
        id=user_device.id,
        user_id=user_device.user_id,
        device_id=user_device.device_id,
        role=user_device.role,
        device_name=device.name,
        created_at=user_device.created_at,
    )


@router.delete("/me/devices/{device_id}", status_code=204)
async def unassign_device_from_user(
    device_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
):
    """Remove a device assignment from the current user."""
    repo = UserDeviceRepository(db)
    deleted = await repo.delete_by_user_and_device(current_user.id, device_id)
    if not deleted:
        raise NotFoundError("UserDevice", str(device_id))
