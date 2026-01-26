"""Core module for security, exceptions, telemetry, and utilities."""

from app.core.exceptions import NotFoundError, WhatsAppAPIError
from app.core.security import generate_api_key, hash_api_key, verify_api_key
from app.core.telemetry import get_tracer, setup_all_instrumentation, setup_telemetry

__all__ = [
    "NotFoundError",
    "WhatsAppAPIError",
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    "get_tracer",
    "setup_telemetry",
    "setup_all_instrumentation",
]
