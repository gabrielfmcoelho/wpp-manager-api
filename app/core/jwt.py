"""Token validation for Logto tokens (JWT and opaque)."""

import logging
from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt
from cachetools import TTLCache
from jwt import PyJWKClient, PyJWKClientError

from app.config import settings

logger = logging.getLogger(__name__)

# Cache for JWKS keys with TTL
_jwks_cache: TTLCache = TTLCache(maxsize=10, ttl=settings.LOGTO_JWKS_CACHE_TTL)

# Cache for userinfo responses (short TTL to balance security and performance)
_userinfo_cache: TTLCache = TTLCache(maxsize=100, ttl=60)  # 1 minute cache


@dataclass
class LogtoUserInfo:
    """User information extracted from Logto token claims."""

    sub: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None


class JWTValidationError(Exception):
    """Raised when token validation fails."""

    pass


@lru_cache(maxsize=1)
def _get_jwks_url() -> str:
    """Get the JWKS URL from Logto's OIDC discovery endpoint."""
    return f"{settings.LOGTO_ENDPOINT}/oidc/jwks"


@lru_cache(maxsize=1)
def _get_userinfo_url() -> str:
    """Get the userinfo URL for Logto."""
    return f"{settings.LOGTO_ENDPOINT}/oidc/me"


def _get_jwks_client() -> PyJWKClient:
    """Get or create a cached JWKS client for Logto."""
    cache_key = "jwks_client"

    if cache_key in _jwks_cache:
        return _jwks_cache[cache_key]

    jwks_url = _get_jwks_url()
    client = PyJWKClient(jwks_url, cache_keys=True)
    _jwks_cache[cache_key] = client
    return client


def _is_jwt(token: str) -> bool:
    """Check if a token looks like a JWT (has 3 dot-separated segments)."""
    return token.count(".") == 2


async def _validate_jwt_token(token: str) -> dict:
    """
    Validate a JWT token and return the claims.

    Args:
        token: The JWT token to validate

    Returns:
        The decoded JWT claims

    Raises:
        JWTValidationError: If the token is invalid
    """
    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and validate the token
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.LOGTO_APP_ID,
            issuer=f"{settings.LOGTO_ENDPOINT}/oidc",
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
        return claims

    except PyJWKClientError as e:
        logger.warning(f"Failed to get signing key from JWKS: {e}")
        raise JWTValidationError(f"Failed to get signing key: {e}") from e
    except jwt.ExpiredSignatureError:
        logger.debug("Token has expired")
        raise JWTValidationError("Token has expired")
    except jwt.InvalidAudienceError:
        logger.warning("Token has invalid audience")
        raise JWTValidationError("Token has invalid audience")
    except jwt.InvalidIssuerError:
        logger.warning("Token has invalid issuer")
        raise JWTValidationError("Token has invalid issuer")
    except jwt.PyJWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise JWTValidationError(f"Token validation failed: {e}") from e


async def _validate_opaque_token(token: str) -> dict:
    """
    Validate an opaque token by calling Logto's userinfo endpoint.

    Args:
        token: The opaque access token to validate

    Returns:
        The user info claims from Logto

    Raises:
        JWTValidationError: If the token is invalid
    """
    # Check cache first
    if token in _userinfo_cache:
        return _userinfo_cache[token]

    userinfo_url = _get_userinfo_url()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )

            if response.status_code == 401:
                raise JWTValidationError("Invalid or expired token")

            if response.status_code != 200:
                logger.warning(
                    f"Userinfo request failed with status {response.status_code}: {response.text}"
                )
                raise JWTValidationError(f"Userinfo request failed: {response.status_code}")

            claims = response.json()

            # Cache the result
            _userinfo_cache[token] = claims

            return claims

    except httpx.RequestError as e:
        logger.error(f"Failed to call userinfo endpoint: {e}")
        raise JWTValidationError(f"Failed to validate token: {e}") from e


async def validate_logto_token(token: str) -> dict:
    """
    Validate a Logto token (JWT or opaque) and return the claims.

    This function automatically detects whether the token is a JWT or opaque
    and uses the appropriate validation method:
    - JWT tokens: Validated locally using JWKS
    - Opaque tokens: Validated by calling Logto's userinfo endpoint

    Args:
        token: The token to validate

    Returns:
        The decoded/fetched claims

    Raises:
        JWTValidationError: If the token is invalid
    """
    if _is_jwt(token):
        logger.debug("Validating JWT token")
        return await _validate_jwt_token(token)
    else:
        logger.debug("Validating opaque token via userinfo endpoint")
        return await _validate_opaque_token(token)


def extract_user_info_from_claims(claims: dict) -> LogtoUserInfo:
    """
    Extract user information from token claims.

    Args:
        claims: The decoded token claims

    Returns:
        LogtoUserInfo with extracted user data
    """
    return LogtoUserInfo(
        sub=claims["sub"],
        email=claims.get("email"),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )


async def get_user_info_from_token(token: str) -> LogtoUserInfo:
    """
    Validate token and extract user info in one call.

    Args:
        token: The token to validate

    Returns:
        LogtoUserInfo with the user's information

    Raises:
        JWTValidationError: If the token is invalid
    """
    claims = await validate_logto_token(token)
    return extract_user_info_from_claims(claims)
