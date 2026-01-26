"""Settings API endpoints."""

from fastapi import APIRouter

from app.api.deps import CurrentAuthContext, DbSession
from app.db.repositories.global_settings import GlobalSettingsRepository
from app.schemas.settings import OpenAISettingsResponse, OpenAISettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

# Key used to store OpenAI settings in global_settings table
OPENAI_SETTINGS_KEY = "openai"

# Default OpenAI settings
DEFAULT_OPENAI_SETTINGS = {
    "use_default": True,
    "api_key": None,
    "host_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
}


@router.get("/openai", response_model=OpenAISettingsResponse)
async def get_openai_settings(
    db: DbSession,
    auth: CurrentAuthContext,
) -> OpenAISettingsResponse:
    """Get current OpenAI settings."""
    repo = GlobalSettingsRepository(db)
    settings = await repo.get_by_key(OPENAI_SETTINGS_KEY)

    if settings:
        value = settings.value
        return OpenAISettingsResponse(
            use_default=value.get("use_default", True),
            host_url=value.get("host_url", DEFAULT_OPENAI_SETTINGS["host_url"]),
            model=value.get("model", DEFAULT_OPENAI_SETTINGS["model"]),
            has_api_key=bool(value.get("api_key")),
        )

    # Return defaults if no settings exist
    return OpenAISettingsResponse(
        use_default=True,
        host_url=DEFAULT_OPENAI_SETTINGS["host_url"],
        model=DEFAULT_OPENAI_SETTINGS["model"],
        has_api_key=False,
    )


@router.patch("/openai", response_model=OpenAISettingsResponse)
async def update_openai_settings(
    db: DbSession,
    auth: CurrentAuthContext,
    data: OpenAISettingsUpdate,
) -> OpenAISettingsResponse:
    """Update OpenAI settings."""
    repo = GlobalSettingsRepository(db)

    # Build value dict, preserving existing api_key if not provided
    existing = await repo.get_by_key(OPENAI_SETTINGS_KEY)
    existing_value = existing.value if existing else {}

    value = {
        "use_default": data.use_default,
        "host_url": data.host_url,
        "model": data.model,
    }

    # Only update api_key if explicitly provided
    if data.api_key is not None:
        value["api_key"] = data.api_key
    elif "api_key" in existing_value:
        value["api_key"] = existing_value["api_key"]

    await repo.upsert(OPENAI_SETTINGS_KEY, value)

    return OpenAISettingsResponse(
        use_default=value["use_default"],
        host_url=value["host_url"],
        model=value["model"],
        has_api_key=bool(value.get("api_key")),
    )
