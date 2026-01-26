# WhatsApp Management Platform - Backend

A multi-device WhatsApp management platform that enables organizations to connect multiple WhatsApp accounts, send/receive messages, schedule communications, and automate responses with AI agents.

## Features

- **Multi-Device Support**: Connect and manage multiple WhatsApp accounts simultaneously
- **Real-Time Messaging**: Receive messages via WebSocket, send via REST API
- **Message Scheduling**: Schedule messages for future delivery with cron expressions
- **AI Agents**: Automated responses using LangGraph or rule-based matching with contact whitelist filtering
- **Contact Management**: Create, edit, and organize contacts per device with descriptions
- **Ignore Rules**: Filter unwanted messages by contact, group, or keyword
- **Distributed Tracing**: Full observability with OpenTelemetry/SigNoz integration
- **Dual Authentication**: JWT tokens (Logto) for dashboard users + API keys for programmatic access
- **Role-Based Access**: Owner/Admin/Viewer roles for device-level access control

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           WhatsApp API Server                           │
│                        (wpp.inovadata.tech)                            │
└─────────────────────┬───────────────────────────────┬──────────────────┘
                      │ WebSocket                     │ REST API
                      ▼                               ▼
┌─────────────────────────────┐         ┌─────────────────────────────┐
│   WebSocket Listener        │         │      FastAPI Backend        │
│   (websocket_listener.py)   │         │        (main.py)            │
└─────────────┬───────────────┘         └─────────────┬───────────────┘
              │                                       │
              │ publish                               │ query/mutate
              ▼                                       ▼
┌─────────────────────────────┐         ┌─────────────────────────────┐
│        RabbitMQ             │         │       PostgreSQL            │
│    (Message Queue)          │         │       (Database)            │
└─────────────┬───────────────┘         └─────────────────────────────┘
              │ consume                               ▲
              ▼                                       │
┌─────────────────────────────┐                      │
│    Message Consumer         │──────────────────────┘
│  (message_consumer.py)      │
│    + Agent Runner           │
└─────────────────────────────┘

┌─────────────────────────────┐         ┌─────────────────────────────┐
│    Scheduler Worker         │         │          Redis              │
│  (scheduler_worker.py)      │────────▶│    (Cache/Sessions)         │
└─────────────────────────────┘         └─────────────────────────────┘
```

### Components

| Component | Description |
|-----------|-------------|
| **FastAPI Backend** | REST API for device management, contacts, messages, agents |
| **WebSocket Listener** | Connects to WhatsApp API WebSocket for real-time events |
| **Message Consumer** | Processes incoming messages from RabbitMQ queue |
| **Scheduler Worker** | Sends scheduled messages at configured times |
| **Device Manager** | Centralized service for device lifecycle management |

## Tech Stack

- **Framework**: FastAPI (async Python)
- **Database**: PostgreSQL with SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Message Queue**: RabbitMQ (aio-pika)
- **Cache**: Redis
- **Authentication**: JWT (PyJWT) with Logto OIDC + API Keys
- **AI**: LangGraph + OpenAI (optional)
- **Observability**: OpenTelemetry + SigNoz

## Project Structure

```
backend/
├── app/
│   ├── api/v1/           # REST API endpoints
│   │   ├── agents.py
│   │   ├── contacts.py
│   │   ├── devices.py
│   │   ├── messages.py
│   │   ├── schedules.py
│   │   ├── users.py        # User profile & device assignment
│   │   └── webhooks.py
│   ├── core/             # Security, exceptions, telemetry
│   │   ├── jwt.py          # Logto JWT validation
│   │   └── ...
│   ├── db/               # Database session, repositories
│   │   └── repositories/
│   │       ├── user_device.py  # User-device assignments
│   │       └── ...
│   ├── models/           # SQLAlchemy models
│   │   ├── user.py         # User model
│   │   ├── user_device.py  # User-device association
│   │   └── ...
│   ├── schemas/          # Pydantic schemas
│   │   ├── user.py         # User schemas
│   │   └── ...
│   ├── services/         # Business logic
│   │   ├── device_manager.py
│   │   ├── message_service.py
│   │   ├── whatsapp_client.py
│   │   └── agent_runner.py
│   ├── agents/           # AI agents (LangGraph, rule-based)
│   └── workers/          # Background workers
│       ├── message_consumer.py
│       ├── scheduler_worker.py
│       └── websocket_listener.py
├── tests/                # Test suite
├── docs/                 # Documentation
├── alembic/              # Database migrations
├── docker-compose.yml
└── pyproject.toml
```

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- RabbitMQ 3.x
- Redis 7.x

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -e .

# Install with optional dependencies
pip install -e ".[dev]"           # Development tools
pip install -e ".[ai]"            # LangGraph/OpenAI
pip install -e ".[observability]" # Full telemetry
pip install -e ".[dev,ai,observability]"  # All
```

### Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Configure the following environment variables:

```env
# Database (required)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/whatsapp

# Redis (required)
REDIS_URL=redis://localhost:6379/0

# RabbitMQ (required)
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# WhatsApp API (required)
WHATSAPP_API_URL=http://wpp.inovadata.tech
WHATSAPP_API_USER=your_username
WHATSAPP_API_PASSWORD=your_password

# Logto Authentication (required for dashboard)
LOGTO_ENDPOINT=https://identity.inovadata.tech
LOGTO_APP_ID=your_app_id
LOGTO_JWKS_CACHE_TTL=3600

# OpenAI (optional, for AI agents)
OPENAI_API_KEY=sk-...

# Telemetry (optional)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=whatsapp-management-api

# Debug mode (enables /api/docs)
DEBUG=true
```

### Database Setup

```bash
# Run migrations
alembic upgrade head
```

### Running the Application

#### Development Mode

```bash
# Start the API server
uvicorn app.main:app --reload --port 8000

# In separate terminals, start the workers:
python -m app.workers.message_consumer
python -m app.workers.scheduler_worker
python -m app.workers.websocket_listener
```

#### Production Mode (Docker)

```bash
# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### API Documentation

When `DEBUG=true`, API documentation is available at:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- OpenAPI JSON: http://localhost:8000/api/openapi.json

## Testing

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_device_manager.py -v

# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v
```

### Test Coverage

```bash
# Run tests with coverage report
pytest --cov=app --cov-report=html

# View HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── unit/                          # Unit tests
│   ├── test_device_manager.py     # DeviceManager service
│   ├── test_whatsapp_client.py    # WhatsApp client
│   ├── test_device_repository.py  # Device repository
│   └── test_message_repository.py # Message repository
└── integration/                   # Integration tests
    └── test_websocket_listener.py # WebSocket worker
```

## Authentication

The API supports two authentication methods:

### 1. JWT Authentication (Dashboard Users)

For dashboard users authenticated via Logto. The frontend obtains a JWT access token from Logto and sends it in the `Authorization` header.

```http
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

JWT tokens are validated against Logto's JWKS endpoint. On first use, a `User` record is created automatically with the user's Logto subject, email, name, and profile picture.

Users can be assigned to devices with different roles:
- **OWNER**: Full access to device
- **ADMIN**: Can manage device settings
- **VIEWER**: Read-only access

### 2. API Key Authentication (Programmatic Access)

For programmatic access (scripts, integrations), use the `X-API-Key` header:

```http
X-API-Key: your-api-key
```

API keys are scoped to a specific device and provide full access to that device's data.

### Dual Authentication

All endpoints accept either authentication method. JWT users can access multiple devices (those assigned to them), while API keys are scoped to a single device.

## API Endpoints

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/me` | Get current user profile |
| GET | `/api/v1/users/me/devices` | List devices assigned to user |
| POST | `/api/v1/users/me/devices` | Assign device to user |
| DELETE | `/api/v1/users/me/devices/{id}` | Unassign device from user |

### Devices

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/devices` | List all devices |
| POST | `/api/v1/devices` | Create new device |
| GET | `/api/v1/devices/{id}` | Get device details |
| PATCH | `/api/v1/devices/{id}` | Update device |
| DELETE | `/api/v1/devices/{id}` | Delete device |
| GET | `/api/v1/devices/{id}/status` | Get connection status |
| POST | `/api/v1/devices/{id}/login` | Initiate QR login |
| POST | `/api/v1/devices/{id}/logout` | Logout device |

### Contacts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/contacts` | List contacts (supports `device_id` filter or all user devices) |
| POST | `/api/v1/contacts` | Create new contact with phone number, name, and description |
| GET | `/api/v1/contacts/{id}` | Get contact details |
| PATCH | `/api/v1/contacts/{id}` | Update contact (name, description, is_blocked) |
| POST | `/api/v1/contacts/{id}/block` | Block contact |
| DELETE | `/api/v1/contacts/{id}/block` | Unblock contact |

### Messages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/messages` | List messages |
| POST | `/api/v1/messages` | Send message |
| GET | `/api/v1/messages/{id}` | Get message details |

### Scheduled Messages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/schedules` | List scheduled messages |
| POST | `/api/v1/schedules` | Create scheduled message |
| PATCH | `/api/v1/schedules/{id}` | Update schedule |
| DELETE | `/api/v1/schedules/{id}` | Cancel schedule |

### Agents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/agents` | List agents |
| POST | `/api/v1/agents` | Create agent |
| GET | `/api/v1/agents/{id}` | Get agent config |
| PATCH | `/api/v1/agents/{id}` | Update agent |
| DELETE | `/api/v1/agents/{id}` | Delete agent |

### Ignore Rules

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/ignore-rules` | List ignore rules |
| POST | `/api/v1/ignore-rules` | Create ignore rule |
| DELETE | `/api/v1/ignore-rules/{id}` | Delete ignore rule |

## Device Login Flow

1. **Create Device**: `POST /api/v1/devices` with device name
2. **Initiate Login**: `POST /api/v1/devices/{id}/login` returns QR code
3. **Scan QR Code**: User scans with WhatsApp mobile app
4. **Check Status**: `GET /api/v1/devices/{id}/status` verifies connection
5. **Ready**: Device is connected, WebSocket listener starts receiving messages

## Agent Types

### Rule-Based Agent

Simple keyword matching with predefined responses:

```json
{
  "name": "FAQ Bot",
  "agent_type": "rule_based",
  "config": {
    "rules": [
      {"pattern": "hello|hi|hey", "response": "Hello! How can I help you?"},
      {"pattern": "hours|schedule", "response": "We're open Mon-Fri 9am-6pm."}
    ],
    "allowed_contacts": ["uuid-1", "uuid-2"],
    "ignore_groups": true
  }
}
```

### LangGraph Agent

AI-powered conversational agent:

```json
{
  "name": "Support Agent",
  "agent_type": "langgraph",
  "config": {
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "system_prompt": "You are a helpful customer support agent.",
    "trigger_keywords": ["help", "support", "question"],
    "allowed_contacts": [],
    "ignore_groups": false
  }
}
```

### Agent Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `rules` | array | Rule-based: List of pattern/response pairs |
| `model` | string | LangGraph: OpenAI model (e.g., "gpt-4o-mini") |
| `temperature` | number | LangGraph: Response creativity (0-2) |
| `system_prompt` | string | LangGraph: Agent instructions |
| `trigger_keywords` | array | Keywords that activate the agent |
| `allowed_contacts` | array | Contact UUIDs that can trigger this agent (empty = all) |
| `ignore_groups` | boolean | Skip messages from group chats |

## Observability

### OpenTelemetry Integration

The application includes full OpenTelemetry instrumentation:

- FastAPI request tracing
- SQLAlchemy query tracing
- httpx outbound request tracing
- aio-pika RabbitMQ tracing
- Redis operation tracing

### Viewing Traces

1. Set up SigNoz or any OpenTelemetry-compatible collector
2. Configure `OTEL_EXPORTER_OTLP_ENDPOINT` in `.env`
3. Traces are automatically exported

## Development

### Code Style

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## License

Proprietary - InovaData

## Support

For issues and feature requests, contact the development team.
