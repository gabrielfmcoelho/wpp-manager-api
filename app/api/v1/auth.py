"""API key management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.config import settings
from app.core.exceptions import NotFoundError
from app.core.security import generate_api_key, hash_api_key
from app.db.repositories import ApiKeyRepository, DeviceRepository
from app.schemas import ApiKeyCreate, ApiKeyDetail, ApiKeyList, ApiKeyResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=201)
async def create_api_key(
    data: ApiKeyCreate,
    db: DbSession,
):
    """Create a new API key for a device.

    The actual key is only returned once during creation.
    Store it securely as it cannot be retrieved again.
    """
    # Verify device exists
    device_repo = DeviceRepository(db)
    device = await device_repo.get(data.device_id)
    if not device:
        raise NotFoundError("Device", str(data.device_id))

    # Generate the API key
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[: len(settings.API_KEY_PREFIX) + 8]

    # Create the API key record
    api_key_repo = ApiKeyRepository(db)
    api_key = await api_key_repo.create(
        device_id=data.device_id,
        name=data.name,
        description=data.description,
        key_hash=key_hash,
        key_prefix=key_prefix,
        expires_at=data.expires_at,
    )

    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,  # Only time we return the actual key
        key_prefix=key_prefix,
        device_id=api_key.device_id,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("/api-keys", response_model=ApiKeyList)
async def list_api_keys(
    db: DbSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    device_id: UUID | None = None,
    is_active: bool | None = None,
):
    """List API keys with optional filtering."""
    repo = ApiKeyRepository(db)
    items, total = await repo.list(
        skip=skip,
        limit=limit,
        device_id=device_id,
        is_active=is_active,
    )
    return ApiKeyList(items=items, total=total, skip=skip, limit=limit)


@router.delete("/api-keys/{api_key_id}", status_code=204)
async def revoke_api_key(
    api_key_id: UUID,
    db: DbSession,
):
    """Revoke an API key."""
    repo = ApiKeyRepository(db)
    api_key = await repo.get(api_key_id)
    if not api_key:
        raise NotFoundError("API Key", str(api_key_id))

    await repo.revoke(api_key_id)
