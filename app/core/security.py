"""Security utilities for API key management."""

import secrets
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ApiKey


def generate_api_key() -> str:
    """Generate a new API key with prefix."""
    random_part = secrets.token_urlsafe(32)
    return f"{settings.API_KEY_PREFIX}{random_part}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key using bcrypt."""
    return bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()


def verify_api_key_hash(api_key: str, hashed: str) -> bool:
    """Verify an API key against its hash."""
    return bcrypt.checkpw(api_key.encode(), hashed.encode())


async def verify_api_key(db: AsyncSession, api_key: str) -> ApiKey | None:
    """Verify an API key and return the ApiKey model if valid."""
    if not api_key.startswith(settings.API_KEY_PREFIX):
        return None

    # Extract the prefix part for lookup (first 8 chars after the prefix)
    key_prefix = api_key[: len(settings.API_KEY_PREFIX) + 8]

    # Find potential matches by prefix
    stmt = select(ApiKey).where(
        ApiKey.key_prefix == key_prefix,
        ApiKey.is_active == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    potential_keys = result.scalars().all()

    # Verify the full key hash
    for potential_key in potential_keys:
        if verify_api_key_hash(api_key, potential_key.key_hash):
            # Check expiration
            if potential_key.expires_at and potential_key.expires_at < datetime.now(timezone.utc):
                return None

            # Update last used timestamp
            potential_key.last_used_at = datetime.now(timezone.utc)
            await db.commit()

            return potential_key

    return None
