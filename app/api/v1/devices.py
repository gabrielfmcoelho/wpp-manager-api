"""Device management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAuthContext, DbSession, OptionalAuthContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.repositories import DeviceRepository, UserDeviceRepository
from app.models.user_device import DeviceRole
from app.schemas import DeviceCreate, DeviceDetail, DeviceList, DeviceStatus, DeviceUpdate
from app.services import WhatsAppClient

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=DeviceList)
async def list_devices(
    db: DbSession,
    auth: OptionalAuthContext,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_active: bool | None = None,
):
    """
    List devices.

    For authenticated users (JWT): Returns only devices they have access to.
    For API key auth: Returns only the device associated with the API key.
    For unauthenticated requests: Returns all devices (for device setup).
    """
    repo = DeviceRepository(db)

    # If authenticated, filter by accessible devices
    if auth.is_authenticated and auth.device_ids:
        items, total = await repo.list_by_ids(
            device_ids=auth.device_ids,
            skip=skip,
            limit=limit,
            is_active=is_active,
        )
    else:
        # Unauthenticated or no devices - return all (for setup)
        items, total = await repo.list(skip=skip, limit=limit, is_active=is_active)

    return DeviceList(items=items, total=total, skip=skip, limit=limit)


@router.post("", response_model=DeviceDetail, status_code=201)
async def create_device(
    data: DeviceCreate,
    db: DbSession,
    auth: OptionalAuthContext,
):
    """
    Create a new device.

    If authenticated via JWT, the device is automatically assigned to the user as owner.
    """
    repo = DeviceRepository(db)
    device = await repo.create(name=data.name)

    # Auto-assign to authenticated user as owner
    if auth.user:
        ud_repo = UserDeviceRepository(db)
        await ud_repo.create(
            user_id=auth.user.id,
            device_id=device.id,
            role=DeviceRole.OWNER,
        )

    return device


@router.get("/{device_id}", response_model=DeviceDetail)
async def get_device(
    device_id: UUID,
    db: DbSession,
    auth: OptionalAuthContext,
):
    """Get device details."""
    repo = DeviceRepository(db)
    device = await repo.get(device_id)
    if not device:
        raise NotFoundError("Device", str(device_id))

    # Check access if authenticated
    if auth.is_authenticated and not auth.has_device_access(device_id):
        raise ForbiddenError("You do not have access to this device")

    return device


@router.patch("/{device_id}", response_model=DeviceDetail)
async def update_device(
    device_id: UUID,
    data: DeviceUpdate,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Update device details."""
    # Check access
    if not auth.has_device_access(device_id):
        raise ForbiddenError("You do not have access to this device")

    repo = DeviceRepository(db)
    device = await repo.get(device_id)
    if not device:
        raise NotFoundError("Device", str(device_id))

    update_data = data.model_dump(exclude_unset=True)
    device = await repo.update(device, **update_data)
    return device


@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Delete a device."""
    # Check access
    if not auth.has_device_access(device_id):
        raise ForbiddenError("You do not have access to this device")

    repo = DeviceRepository(db)
    device = await repo.get(device_id)
    if not device:
        raise NotFoundError("Device", str(device_id))

    await repo.delete(device)


@router.get("/{device_id}/status", response_model=DeviceStatus)
async def get_device_status(
    device_id: UUID,
    db: DbSession,
    auth: OptionalAuthContext,
):
    """Get device connection status from WhatsApp API and sync WhatsApp info."""
    # Check access if authenticated
    if auth.is_authenticated and not auth.has_device_access(device_id):
        raise ForbiddenError("You do not have access to this device")

    repo = DeviceRepository(db)
    device = await repo.get(device_id)
    if not device:
        raise NotFoundError("Device", str(device_id))

    # Try to get status from WhatsApp API
    client = WhatsAppClient(str(device_id))
    try:
        status = await client.get_status()
        is_connected = status.get("connected", False)
        is_logged_in = status.get("logged_in", False)
        jid = status.get("jid") or status.get("wid")

        # Extract phone number from JID (format: 5511999999999@s.whatsapp.net)
        phone_number = None
        if jid and "@" in jid:
            phone_number = jid.split("@")[0]

        # Update device with WhatsApp info
        device = await repo.update_whatsapp_info(
            device_id,
            whatsapp_id=jid if jid else device.whatsapp_id,
            phone_number=phone_number if phone_number else device.phone_number,
            is_connected=is_connected and is_logged_in,
        )

        return DeviceStatus(
            id=device.id,
            name=device.name,
            is_connected=device.is_connected,
            phone_number=device.phone_number,
        )
    except Exception:
        return DeviceStatus(
            id=device.id,
            name=device.name,
            is_connected=False,
            phone_number=device.phone_number,
        )


@router.post("/{device_id}/login")
async def initiate_login(
    device_id: UUID,
    db: DbSession,
    auth: OptionalAuthContext,
):
    """Initiate QR code login for a device."""
    # Check access if authenticated
    if auth.is_authenticated and not auth.has_device_access(device_id):
        raise ForbiddenError("You do not have access to this device")

    repo = DeviceRepository(db)
    device = await repo.get(device_id)
    if not device:
        raise NotFoundError("Device", str(device_id))

    client = WhatsAppClient(str(device_id))
    qr_data = await client.get_qr_code()

    return {"device_id": str(device_id), "qr": qr_data}


@router.post("/{device_id}/login/code")
async def initiate_login_with_code(
    device_id: UUID,
    phone: str = Query(..., description="Phone number to pair with (e.g., 5511999999999)"),
    db: DbSession = None,
    auth: OptionalAuthContext = None,
):
    """
    Initiate pairing code login for a device.

    Instead of scanning a QR code, users can enter a pairing code
    in WhatsApp > Linked Devices > Link a Device > Link with phone number instead.
    """
    # Check access if authenticated
    if auth.is_authenticated and not auth.has_device_access(device_id):
        raise ForbiddenError("You do not have access to this device")

    repo = DeviceRepository(db)
    device = await repo.get(device_id)
    if not device:
        raise NotFoundError("Device", str(device_id))

    client = WhatsAppClient(str(device_id))
    result = await client.login_with_code(phone)

    # Extract pairing code from response
    # WhatsApp API returns it as "pair_code" in results
    pairing_code = (
        result.get("results", {}).get("pair_code")
        or result.get("results", {}).get("pairing_code")
        or result.get("pair_code")
        or result.get("pairing_code")
    )

    return {
        "device_id": str(device_id),
        "phone": phone,
        "pairing_code": pairing_code,
        "raw_response": result,
    }


@router.post("/{device_id}/reconnect")
async def reconnect_device(
    device_id: UUID,
    db: DbSession,
    auth: OptionalAuthContext,
):
    """
    Attempt to reconnect a disconnected device.

    This can be used when a device was previously connected but lost connection.
    """
    # Check access if authenticated
    if auth.is_authenticated and not auth.has_device_access(device_id):
        raise ForbiddenError("You do not have access to this device")

    repo = DeviceRepository(db)
    device = await repo.get(device_id)
    if not device:
        raise NotFoundError("Device", str(device_id))

    client = WhatsAppClient(str(device_id))

    try:
        result = await client.reconnect()
        # Update connection status based on result
        is_connected = result.get("connected", False) or result.get("status") == "connected"
        await repo.update_connection_status(device_id, is_connected)

        return {
            "device_id": str(device_id),
            "status": "connected" if is_connected else "reconnecting",
            "raw_response": result,
        }
    except Exception as e:
        return {
            "device_id": str(device_id),
            "status": "failed",
            "error": str(e),
        }


@router.post("/{device_id}/logout")
async def logout_device(
    device_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Logout a device from WhatsApp."""
    # Check access
    if not auth.has_device_access(device_id):
        raise ForbiddenError("You do not have access to this device")

    repo = DeviceRepository(db)
    device = await repo.get(device_id)
    if not device:
        raise NotFoundError("Device", str(device_id))

    client = WhatsAppClient(str(device_id))
    await client.logout()

    # Update local status
    await repo.update_connection_status(device_id, False)

    return {"status": "logged_out", "device_id": str(device_id)}


@router.post("/{device_id}/sync-status")
async def sync_device_status(
    device_id: UUID,
    event: dict,
    db: DbSession,
    auth: OptionalAuthContext,
):
    """
    Sync device status based on a WebSocket event from the WhatsApp API.

    This endpoint is called by the frontend when it receives real-time
    WebSocket events indicating connection status changes.
    """
    # Check access if authenticated
    if auth.is_authenticated and not auth.has_device_access(device_id):
        raise ForbiddenError("You do not have access to this device")

    repo = DeviceRepository(db)
    device = await repo.get(device_id)
    if not device:
        raise NotFoundError("Device", str(device_id))

    # Determine connection status from event
    event_type = (
        event.get("code", "")
        or event.get("event", "")
        or event.get("type", "")
    ).upper()

    is_connected = False
    jid = None
    phone_number = None

    if event_type in ("LIST_DEVICES", "CONNECTED", "READY", "LOGIN_SUCCESS"):
        is_connected = True

        # Try to extract JID from result/results
        result = event.get("result", []) or event.get("results", [])
        if isinstance(result, list) and result:
            device_info = result[0]
            jid = device_info.get("device")
        elif isinstance(result, dict):
            jid = result.get("device") or result.get("jid")

        # Also check message for JID pattern
        if not jid:
            import re
            message = event.get("message", "")
            pattern = r"(\d+(?::\d+)?@s\.whatsapp\.net)"
            match = re.search(pattern, message)
            if match:
                jid = match.group(1)

        # Extract phone number from JID
        if jid and "@" in jid:
            phone_part = jid.split("@")[0]
            phone_number = phone_part.split(":")[0] if ":" in phone_part else phone_part

    elif event_type in ("DISCONNECTED", "LOGOUT"):
        is_connected = False

    # Update device status
    await repo.update_whatsapp_info(
        device_id,
        whatsapp_id=jid if jid else device.whatsapp_id,
        phone_number=phone_number if phone_number else device.phone_number,
        is_connected=is_connected,
    )

    return {
        "device_id": str(device_id),
        "is_connected": is_connected,
        "whatsapp_id": jid or device.whatsapp_id,
        "phone_number": phone_number or device.phone_number,
        "event_type": event_type,
    }
