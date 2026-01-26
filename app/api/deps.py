"""Common API dependencies."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.jwt import JWTValidationError, get_user_info_from_token, LogtoUserInfo
from app.core.security import verify_api_key
from app.db.session import async_session_maker
from app.models import ApiKey, User, UserDevice


# Optional HTTP Bearer auth - allows both authenticated and unauthenticated requests
optional_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Dependency for getting async Redis client."""
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.close()


async def get_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """Dependency for validating API key and getting the ApiKey model."""
    if not x_api_key:
        raise UnauthorizedError("Missing X-API-Key header")

    api_key = await verify_api_key(db, x_api_key)
    if not api_key:
        raise UnauthorizedError("Invalid API key")

    return api_key


async def get_optional_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> ApiKey | None:
    """Dependency for optionally validating API key."""
    if not x_api_key:
        return None

    return await verify_api_key(db, x_api_key)


async def get_or_create_user(db: AsyncSession, user_info: LogtoUserInfo) -> User:
    """
    Find or create a user from Logto JWT claims.

    Handles race conditions where multiple requests try to create
    the same user simultaneously.

    Args:
        db: Database session
        user_info: User information from Logto token

    Returns:
        The User model instance
    """
    from sqlalchemy.exc import IntegrityError

    # Try to find existing user by logto_sub
    stmt = (
        select(User)
        .where(User.logto_sub == user_info.sub)
        .options(selectinload(User.user_devices).selectinload(UserDevice.device))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Update last login and any changed profile info
        user.last_login_at = datetime.now(timezone.utc)
        if user_info.email and user.email != user_info.email:
            user.email = user_info.email
        if user_info.name and user.name != user_info.name:
            user.name = user_info.name
        if user_info.picture and user.picture != user_info.picture:
            user.picture = user_info.picture
        await db.commit()
        await db.refresh(user)
        return user

    # Try to create new user
    try:
        user = User(
            logto_sub=user_info.sub,
            email=user_info.email,
            name=user_info.name,
            picture=user_info.picture,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user, attribute_names=["user_devices"])
        return user
    except IntegrityError:
        # Race condition: another request created the user first
        # Rollback and fetch the existing user
        await db.rollback()
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            return user
        # If still not found, re-raise (shouldn't happen)
        raise


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(optional_bearer)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency for getting current user from JWT token.

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        The authenticated User

    Raises:
        UnauthorizedError: If token is missing or invalid
    """
    if not credentials:
        raise UnauthorizedError("Missing authorization header")

    try:
        user_info = await get_user_info_from_token(credentials.credentials)
    except JWTValidationError as e:
        raise UnauthorizedError(str(e))

    return await get_or_create_user(db, user_info)


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(optional_bearer)],
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    Dependency for optionally getting current user from JWT token.
    Returns None if no valid token is provided.
    """
    if not credentials:
        return None

    try:
        user_info = await get_user_info_from_token(credentials.credentials)
        return await get_or_create_user(db, user_info)
    except JWTValidationError:
        return None


@dataclass
class AuthContext:
    """
    Unified authentication context supporting both JWT and API key auth.

    This class provides a consistent interface for accessing authentication
    information regardless of whether the request used JWT or API key auth.
    """

    user: User | None = None
    api_key: ApiKey | None = None

    @property
    def is_authenticated(self) -> bool:
        """Check if the context represents an authenticated request."""
        return self.user is not None or self.api_key is not None

    @property
    def device_ids(self) -> list[UUID]:
        """
        Get the list of device IDs accessible to this auth context.

        For JWT auth: Returns devices the user has access to via user_devices.
        For API key auth: Returns only the device associated with the API key.
        """
        if self.api_key:
            return [self.api_key.device_id]

        if self.user and self.user.user_devices:
            return [ud.device_id for ud in self.user.user_devices]

        return []

    def has_device_access(self, device_id: UUID) -> bool:
        """Check if this auth context has access to a specific device."""
        return device_id in self.device_ids


async def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(optional_bearer)],
    x_api_key: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """
    Dependency for getting unified authentication context.

    Supports both JWT Bearer tokens and X-API-Key headers.
    JWT takes precedence if both are provided.

    Args:
        credentials: HTTP Bearer credentials (JWT)
        x_api_key: API key header
        db: Database session

    Returns:
        AuthContext with user and/or api_key populated

    Raises:
        UnauthorizedError: If no valid authentication is provided
    """
    user = None
    api_key = None

    # Try JWT auth first (takes precedence)
    if credentials:
        try:
            user_info = await get_user_info_from_token(credentials.credentials)
            user = await get_or_create_user(db, user_info)
        except JWTValidationError:
            # JWT provided but invalid - don't fall back to API key
            raise UnauthorizedError("Invalid JWT token")

    # Try API key if no JWT
    if not user and x_api_key:
        api_key = await verify_api_key(db, x_api_key)
        if not api_key:
            raise UnauthorizedError("Invalid API key")

    # Require at least one auth method
    if not user and not api_key:
        raise UnauthorizedError("Authentication required")

    return AuthContext(user=user, api_key=api_key)


async def get_optional_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(optional_bearer)],
    x_api_key: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """
    Dependency for getting optional authentication context.

    Returns an unauthenticated AuthContext if no valid credentials are provided.
    Does not raise errors for missing authentication.
    """
    user = None
    api_key = None

    # Try JWT auth first
    if credentials:
        try:
            user_info = await get_user_info_from_token(credentials.credentials)
            user = await get_or_create_user(db, user_info)
        except JWTValidationError:
            pass  # Invalid JWT, try API key

    # Try API key if no JWT
    if not user and x_api_key:
        api_key = await verify_api_key(db, x_api_key)

    return AuthContext(user=user, api_key=api_key)


# Type aliases for cleaner annotations
DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
CurrentApiKey = Annotated[ApiKey, Depends(get_api_key)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAuthContext = Annotated[AuthContext, Depends(get_auth_context)]
OptionalAuthContext = Annotated[AuthContext, Depends(get_optional_auth_context)]
