# WebSocket Client & Device Login Flow - Implementation Plan

## Status: COMPLETED

Last Updated: 2026-01-25

---

## Overview

Implementation of a WebSocket client worker to receive messages from the WhatsApp API, and enhancement of the device login flow to properly save device information.

---

## Implementation Checklist

### 1. WebSocket Dependencies
- [x] Add `websockets>=13.0.0` to `pyproject.toml`

### 2. WebSocket Client Worker
- [x] Create `app/workers/websocket_listener.py`
- [x] `DeviceConnection` class for single device WebSocket management
- [x] `WebSocketManager` class for multi-device coordination
- [x] Event handlers: message, message.ack, connected, disconnected, qr
- [x] Auto-reconnect with exponential backoff
- [x] Publish incoming messages to RabbitMQ queue

### 3. WhatsApp Client Enhancements
- [x] Add `get_websocket_url()` method
- [x] Add `get_auth_header()` method for WebSocket auth

### 4. Device Repository Enhancements
- [x] Add `update_whatsapp_info()` method
- [x] Add `get_active_devices()` method

### 5. Device API Enhancements
- [x] Enhance `get_device_status` endpoint to sync WhatsApp JID
- [x] Extract and save phone number from JID

### 6. Message Repository Enhancements
- [x] Add `update_status_by_whatsapp_id()` method

### 7. Device Manager Service
- [x] Create `app/services/device_manager.py`
- [x] `register_device()` - Register new device
- [x] `initiate_login()` - Start QR login flow
- [x] `complete_login()` - Verify login after QR scan
- [x] `sync_status()` - Sync status from WhatsApp API
- [x] `disconnect_device()` - Logout from WhatsApp
- [x] `deactivate_device()` - Soft delete device
- [x] `reactivate_device()` - Reactivate device
- [x] `get_connection_info()` - Get detailed connection info

### 8. Telemetry (OpenTelemetry/SigNoz)
- [x] Create `app/core/telemetry.py`
- [x] FastAPI instrumentation
- [x] Optional instrumentations: httpx, SQLAlchemy, aio-pika, Redis
- [x] Add observability optional dependencies

### 9. Docker Compose
- [x] Create `docker-compose.yml` for API + Workers
- [x] Services: api, message-consumer, scheduler, websocket-listener

---

## Files Created

| File | Description |
|------|-------------|
| `app/workers/websocket_listener.py` | WebSocket client worker |
| `app/services/device_manager.py` | Device lifecycle management |
| `app/core/telemetry.py` | OpenTelemetry setup |
| `docker-compose.yml` | Docker Compose for services |

## Files Modified

| File | Changes |
|------|---------|
| `pyproject.toml` | Added websockets, observability deps |
| `app/services/whatsapp_client.py` | WebSocket URL helpers |
| `app/db/repositories/device.py` | WhatsApp info methods |
| `app/db/repositories/message.py` | Status update by WhatsApp ID |
| `app/api/v1/devices.py` | Enhanced status endpoint |
| `app/main.py` | Telemetry setup in lifespan |
| `app/core/__init__.py` | Export telemetry |
| `app/services/__init__.py` | Export DeviceManager |

## Test Files Created

| File | Description |
|------|-------------|
| `tests/conftest.py` | Pytest fixtures and configuration |
| `tests/unit/test_device_manager.py` | DeviceManager service tests |
| `tests/unit/test_whatsapp_client.py` | WhatsAppClient tests |
| `tests/unit/test_device_repository.py` | DeviceRepository tests |
| `tests/unit/test_message_repository.py` | MessageRepository tests |
| `tests/integration/test_websocket_listener.py` | WebSocket listener tests |

---

## Test Plan

### Unit Tests

#### 1. Device Manager Tests (`tests/unit/test_device_manager.py`) - CREATED
- [x] `test_register_device` - Creates device with correct name
- [x] `test_get_device` - Gets existing device
- [x] `test_get_device_not_found` - Raises NotFoundError
- [x] `test_initiate_login` - Returns QR data
- [x] `test_sync_status_connected` - Updates device with JID
- [x] `test_sync_status_disconnected` - Handles disconnected state
- [x] `test_sync_status_api_error` - Marks disconnected on error
- [x] `test_disconnect_device` - Calls logout and updates status
- [x] `test_deactivate_device` - Disconnects and sets inactive
- [x] `test_reactivate_device` - Sets device active
- [x] `test_get_connection_info` - Gets detailed connection info

#### 2. WhatsApp Client Tests (`tests/unit/test_whatsapp_client.py`) - CREATED
- [x] `test_get_websocket_url_http` - Returns ws:// URL
- [x] `test_get_websocket_url_https` - Returns wss:// URL
- [x] `test_get_websocket_url_with_port` - Handles URL with port
- [x] `test_get_auth_header_with_credentials` - Returns correct Basic auth header
- [x] `test_get_auth_header_no_credentials` - Returns None
- [x] `test_client_initialization` - Stores device ID correctly

#### 3. Device Repository Tests (`tests/unit/test_device_repository.py`) - CREATED
- [x] `test_update_whatsapp_info_all_fields` - Updates all fields
- [x] `test_update_whatsapp_info_partial` - Updates only provided fields
- [x] `test_update_whatsapp_info_not_found` - Returns None for missing device
- [x] `test_get_active_devices` - Returns only active devices
- [x] `test_update_connection_status` - Updates connection status
- [x] `test_get_by_whatsapp_id` - Gets device by WhatsApp ID
- [x] `test_get_by_whatsapp_id_not_found` - Returns None

#### 4. Message Repository Tests (`tests/unit/test_message_repository.py`) - CREATED
- [x] `test_update_status_by_whatsapp_id` - Updates status correctly
- [x] `test_update_status_by_whatsapp_id_to_read` - Updates to read status
- [x] `test_update_status_by_whatsapp_id_not_found` - Returns None
- [x] `test_update_status_by_whatsapp_id_invalid_status` - Handles invalid status
- [x] `test_get_by_whatsapp_id` - Gets message by WhatsApp ID
- [x] `test_update_status` - Updates status by message ID

### Integration Tests

#### 5. WebSocket Listener Tests (`tests/integration/test_websocket_listener.py`) - CREATED
- [x] `test_handle_message_event_publishes_to_queue` - Publishes to RabbitMQ
- [x] `test_handle_connected_event_updates_status` - Updates device status
- [x] `test_handle_disconnected_event_updates_status` - Updates device status
- [x] `test_handle_message_ack_event` - Updates message status
- [x] `test_get_websocket_url` - WebSocket URL in connection
- [x] `test_websocket_manager_add_device` - Creates connection
- [x] `test_websocket_manager_add_device_skips_duplicate` - Skips duplicates
- [x] `test_websocket_manager_remove_device` - Closes connection
- [x] `test_websocket_manager_load_devices` - Loads from database
- [x] `test_websocket_manager_close` - Removes all connections

#### 6. Device API Tests (`tests/integration/test_devices_api.py`) - TODO
- [ ] `test_get_device_status_syncs_jid` - Saves WhatsApp ID
- [ ] `test_get_device_status_extracts_phone` - Parses phone from JID

### End-to-End Tests

#### 7. Device Login Flow (`tests/e2e/test_device_login_flow.py`) - TODO
- [ ] `test_full_login_flow` - Create device → Login → Verify status

---

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_device_manager.py -v

# Run integration tests only
pytest tests/integration/ -v
```

---

## Running the Services

```bash
# Development (local)
uvicorn app.main:app --reload
python -m app.workers.message_consumer
python -m app.workers.scheduler_worker
python -m app.workers.websocket_listener

# Production (Docker)
docker compose up -d --build
docker compose logs -f
```

---

## Configuration

Required environment variables:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/whatsapp
REDIS_URL=redis://host:6379/0
RABBITMQ_URL=amqp://guest:guest@host:5672/
WHATSAPP_API_URL=http://wpp.inovadata.tech
WHATSAPP_API_USER=username
WHATSAPP_API_PASSWORD=password
```

Optional:

```env
OPENAI_API_KEY=sk-...
OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4317
DEBUG=true
```
