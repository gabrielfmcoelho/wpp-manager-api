"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/whatsapp"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # WhatsApp API
    WHATSAPP_API_URL: str = "https://wpp.inovadata.tech"
    WHATSAPP_API_USER: str = ""
    WHATSAPP_API_PASSWORD: str = ""

    # Security
    API_KEY_HASH_ALGORITHM: str = "bcrypt"
    API_KEY_PREFIX: str = "wm_"

    # Logto JWT Configuration
    LOGTO_ENDPOINT: str = "https://identity.inovadata.tech"
    LOGTO_APP_ID: str = "5n30475np13ejfuwaskfa"
    LOGTO_JWKS_CACHE_TTL: int = 3600

    # LangGraph / LLM
    OPENAI_API_KEY: str | None = None

    # Telemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "whatsapp-management-api"

    # Debug mode
    DEBUG: bool = False


settings = Settings()
