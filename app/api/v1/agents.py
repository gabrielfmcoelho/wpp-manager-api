"""Agent management endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import CurrentAuthContext, DbSession
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.db.repositories import AgentRepository, VideoDistributionJobRepository
from app.schemas import AgentCreate, AgentDetail, AgentList, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])

VALID_AGENT_TYPES = ["langgraph", "rule_based", "subscription_optin", "video_distributor"]


class DistributeNowResponse(BaseModel):
    """Response from distribute-now endpoint."""

    agent_id: str
    message: str
    next_run_at: str


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


@router.get("", response_model=AgentList)
async def list_agents(
    db: DbSession,
    auth: CurrentAuthContext,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    device_id: UUID | None = Query(None, description="Filter by device ID"),
    is_active: bool | None = None,
    agent_type: str | None = None,
):
    """List agents for authenticated user's devices."""
    target_device_id = _get_device_id_optional(auth, device_id)

    # User has no devices - return empty list
    if target_device_id is None:
        return AgentList(items=[], total=0, skip=skip, limit=limit)

    repo = AgentRepository(db)
    items, total = await repo.list(
        device_id=target_device_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
        agent_type=agent_type,
    )
    return AgentList(items=items, total=total, skip=skip, limit=limit)


@router.post("", response_model=AgentDetail, status_code=201)
async def create_agent(
    data: AgentCreate,
    db: DbSession,
    auth: CurrentAuthContext,
    device_id: UUID | None = Query(None, description="Device to create agent for"),
):
    """Create a new agent."""
    target_device_id = _get_device_id(auth, device_id)

    # Validate agent type
    if data.agent_type not in VALID_AGENT_TYPES:
        raise BadRequestError(f"agent_type must be one of: {VALID_AGENT_TYPES}")

    repo = AgentRepository(db)
    agent = await repo.create(
        device_id=target_device_id,
        name=data.name,
        description=data.description,
        agent_type=data.agent_type,
        config=data.config,
        priority=data.priority,
    )

    # Create distribution job for video_distributor agents
    if data.agent_type == "video_distributor":
        job_repo = VideoDistributionJobRepository(db)
        interval_hours = data.config.get("interval_hours", 24) if data.config else 24
        from datetime import timedelta
        next_run = datetime.now(timezone.utc) + timedelta(hours=interval_hours)
        await job_repo.get_or_create(agent.id, initial_next_run=next_run)

    return agent


@router.get("/{agent_id}", response_model=AgentDetail)
async def get_agent(
    agent_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Get agent details."""
    repo = AgentRepository(db)

    # Try to find agent in any of user's accessible devices
    for device_id in auth.device_ids:
        agent = await repo.get_by_device(device_id, agent_id)
        if agent:
            return agent

    raise NotFoundError("Agent", str(agent_id))


@router.patch("/{agent_id}", response_model=AgentDetail)
async def update_agent(
    agent_id: UUID,
    data: AgentUpdate,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Update agent configuration."""
    repo = AgentRepository(db)

    # Find agent and verify access
    agent = None
    for device_id in auth.device_ids:
        agent = await repo.get_by_device(device_id, agent_id)
        if agent:
            break

    if not agent:
        raise NotFoundError("Agent", str(agent_id))

    update_data = data.model_dump(exclude_unset=True)
    agent = await repo.update(agent, **update_data)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Delete an agent."""
    repo = AgentRepository(db)

    # Find agent and verify access
    agent = None
    for device_id in auth.device_ids:
        agent = await repo.get_by_device(device_id, agent_id)
        if agent:
            break

    if not agent:
        raise NotFoundError("Agent", str(agent_id))

    await repo.delete(agent)


@router.post("/{agent_id}/distribute-now", response_model=DistributeNowResponse)
async def distribute_now(
    agent_id: UUID,
    db: DbSession,
    auth: CurrentAuthContext,
):
    """Trigger immediate video distribution for a video_distributor agent.

    This sets the next_run_at to now, causing the worker to process it
    on its next check cycle.
    """
    agent_repo = AgentRepository(db)
    job_repo = VideoDistributionJobRepository(db)

    # Find agent and verify access
    agent = None
    for device_id in auth.device_ids:
        agent = await agent_repo.get_by_device(device_id, agent_id)
        if agent:
            break

    if not agent:
        raise NotFoundError("Agent", str(agent_id))

    # Verify it's a video_distributor agent
    if agent.agent_type != "video_distributor":
        raise BadRequestError("This endpoint only works with video_distributor agents")

    # Get or create the distribution job
    now = datetime.now(timezone.utc)
    job = await job_repo.get_or_create(agent.id, initial_next_run=now)

    # Set next_run_at to now to trigger immediate distribution
    await job_repo.update_run_times(
        job,
        last_run=job.last_run_at or now,
        next_run=now,
    )

    return DistributeNowResponse(
        agent_id=str(agent.id),
        message="Distribution scheduled for immediate execution",
        next_run_at=now.isoformat(),
    )
