"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import Device


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine():
    """Create async engine for testing."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for testing."""
    async_session_maker = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_device_data() -> dict[str, Any]:
    """Sample device data for testing."""
    return {
        "id": uuid4(),
        "name": "Test Device",
        "phone_number": "5511999999999",
        "whatsapp_id": "5511999999999@s.whatsapp.net",
        "is_connected": False,
        "is_active": True,
    }


@pytest.fixture
async def sample_device(db_session: AsyncSession, sample_device_data) -> Device:
    """Create a sample device in the database."""
    device = Device(**sample_device_data)
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)
    return device


@pytest.fixture
def mock_whatsapp_client():
    """Mock WhatsApp client for testing."""
    client = MagicMock()
    client.get_status = AsyncMock(
        return_value={
            "connected": True,
            "logged_in": True,
            "jid": "5511999999999@s.whatsapp.net",
        }
    )
    client.get_qr_code = AsyncMock(
        return_value={"qr": "base64_qr_code_data", "timeout": 60}
    )
    client.logout = AsyncMock(return_value={"status": "logged_out"})
    client.get_websocket_url = MagicMock(
        return_value="ws://wpp.inovadata.tech/ws?device_id=test"
    )
    client.get_auth_header = MagicMock(
        return_value={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    return client


@pytest.fixture
def mock_rabbitmq_connection():
    """Mock RabbitMQ connection for testing."""
    connection = AsyncMock()
    channel = AsyncMock()
    connection.channel = AsyncMock(return_value=channel)
    channel.declare_queue = AsyncMock()
    channel.default_exchange = AsyncMock()
    channel.default_exchange.publish = AsyncMock()
    return connection


@pytest.fixture
def sample_message_data() -> dict[str, Any]:
    """Sample incoming message data."""
    return {
        "id": "ABCD1234567890",
        "from": "5511888888888@s.whatsapp.net",
        "to": "5511999999999@s.whatsapp.net",
        "body": "Hello, this is a test message",
        "type": "text",
        "timestamp": 1706140800,
    }


@pytest.fixture
def sample_websocket_message_event(sample_message_data) -> dict[str, Any]:
    """Sample WebSocket message event."""
    return {
        "event": "message",
        "data": sample_message_data,
    }


@pytest.fixture
def sample_websocket_ack_event() -> dict[str, Any]:
    """Sample WebSocket message ack event."""
    return {
        "event": "message.ack",
        "data": {
            "id": "ABCD1234567890",
            "ack": 2,  # delivered
        },
    }


@pytest.fixture
def sample_websocket_connected_event() -> dict[str, Any]:
    """Sample WebSocket connected event."""
    return {
        "event": "connected",
        "data": {
            "jid": "5511999999999@s.whatsapp.net",
        },
    }
