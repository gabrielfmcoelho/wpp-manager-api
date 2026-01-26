"""OpenTelemetry/SigNoz telemetry setup for distributed tracing."""

import logging
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_telemetry(app: "FastAPI") -> None:
    """Configure OpenTelemetry tracing for the FastAPI application.

    This sets up:
    - TracerProvider with service name resource
    - OTLP exporter to send traces to SigNoz/collector
    - FastAPI instrumentation for automatic request tracing
    """
    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        logger.info("Telemetry disabled: OTEL_EXPORTER_OTLP_ENDPOINT not configured")
        return

    try:
        # Create resource with service information
        resource = Resource.create(
            {
                "service.name": settings.OTEL_SERVICE_NAME,
                "service.version": "1.0.0",
                "deployment.environment": "development" if settings.DEBUG else "production",
            }
        )

        # Create and set tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)

        # Configure OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            insecure=True,  # Set to False for production with TLS
        )

        # Add batch processor for efficient span export
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=tracer_provider,
            excluded_urls="health,api/docs,api/redoc,api/openapi.json",
        )

        logger.info(
            f"Telemetry enabled: exporting to {settings.OTEL_EXPORTER_OTLP_ENDPOINT}"
        )

    except Exception as e:
        logger.warning(f"Failed to setup telemetry: {e}")


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance for manual span creation.

    Args:
        name: Name of the module/component creating spans

    Returns:
        Tracer instance

    Example:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("operation_name") as span:
            span.set_attribute("key", "value")
            # ... do work ...
    """
    return trace.get_tracer(name)


def instrument_httpx() -> None:
    """Instrument httpx for outbound HTTP tracing."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("httpx instrumentation enabled")
    except ImportError:
        logger.debug("httpx instrumentation not available")


def instrument_sqlalchemy() -> None:
    """Instrument SQLAlchemy for database tracing."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(enable_commenter=True)
        logger.info("SQLAlchemy instrumentation enabled")
    except ImportError:
        logger.debug("SQLAlchemy instrumentation not available")


def instrument_aio_pika() -> None:
    """Instrument aio-pika for RabbitMQ tracing."""
    try:
        from opentelemetry.instrumentation.aio_pika import AioPikaInstrumentor

        AioPikaInstrumentor().instrument()
        logger.info("aio-pika instrumentation enabled")
    except ImportError:
        logger.debug("aio-pika instrumentation not available")


def instrument_redis() -> None:
    """Instrument Redis for cache tracing."""
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
        logger.info("Redis instrumentation enabled")
    except ImportError:
        logger.debug("Redis instrumentation not available")


def setup_all_instrumentation(app: "FastAPI") -> None:
    """Setup telemetry with all available instrumentations.

    This is a convenience function that sets up the base telemetry
    and enables all available instrumentations for comprehensive tracing.
    """
    setup_telemetry(app)

    # Only instrument if telemetry is enabled
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        instrument_httpx()
        instrument_sqlalchemy()
        instrument_aio_pika()
        instrument_redis()
