"""Ignore rule management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAuthContext, DbSession
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.repositories import IgnoreRuleRepository
from app.models.ignore_rule import IgnoreRuleType
from app.schemas import IgnoreRuleCreate, IgnoreRuleDetail, IgnoreRuleList

router = APIRouter(prefix="/ignore-rules", tags=["ignore-rules"])


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


@router.get("", response_model=IgnoreRuleList)
async def list_ignore_rules(
    db: DbSession,
    auth: CurrentAuthContext,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    device_id: UUID | None = Query(None, description="Filter by device ID"),
    rule_type: IgnoreRuleType | None = None,
):
    """List ignore rules for authenticated user's devices."""
    target_device_id = _get_device_id_optional(auth, device_id)

    # User has no devices - return empty list
    if target_device_id is None:
        return IgnoreRuleList(items=[], total=0, skip=skip, limit=limit)

    repo = IgnoreRuleRepository(db)
    items, total = await repo.list(
        device_id=target_device_id,
        skip=skip,
        limit=limit,
        rule_type=rule_type,
    )
    return IgnoreRuleList(items=items, total=total, skip=skip, limit=limit)


@router.post("", response_model=IgnoreRuleDetail, status_code=201)
async def create_ignore_rule(
    data: IgnoreRuleCreate,
    db: DbSession,
    auth: CurrentAuthContext,
    device_id: UUID | None = Query(None, description="Device to create rule for"),
):
    """Create a new ignore rule."""
    target_device_id = _get_device_id(auth, device_id)

    repo = IgnoreRuleRepository(db)
    rule = await repo.create(
        device_id=target_device_id,
        rule_type=data.rule_type,
        pattern=data.pattern,
        reason=data.reason,
    )
    return rule


@router.get("/{rule_id}", response_model=IgnoreRuleDetail)
async def get_ignore_rule(
    rule_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Get ignore rule details."""
    repo = IgnoreRuleRepository(db)

    # Try to find rule in any of user's accessible devices
    for device_id in auth.device_ids:
        rule = await repo.get_by_device(device_id, rule_id)
        if rule:
            return rule

    raise NotFoundError("Ignore Rule", str(rule_id))


@router.delete("/{rule_id}", status_code=204)
async def delete_ignore_rule(
    rule_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Delete an ignore rule."""
    repo = IgnoreRuleRepository(db)

    # Find rule and verify access
    rule = None
    for device_id in auth.device_ids:
        rule = await repo.get_by_device(device_id, rule_id)
        if rule:
            break

    if not rule:
        raise NotFoundError("Ignore Rule", str(rule_id))

    await repo.delete(rule)
