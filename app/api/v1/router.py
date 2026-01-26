"""Main API router aggregating all v1 routes."""

from fastapi import APIRouter

from app.api.v1 import (
    agents,
    auth,
    contacts,
    debug,
    devices,
    ignore_rules,
    messages,
    schedules,
    settings,
    users,
    webhooks,
)

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(devices.router)
api_router.include_router(contacts.router)
api_router.include_router(messages.router)
api_router.include_router(schedules.router)
api_router.include_router(agents.router)
api_router.include_router(ignore_rules.router)
api_router.include_router(settings.router)
api_router.include_router(webhooks.router)
api_router.include_router(debug.router)
