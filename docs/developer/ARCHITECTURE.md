# Astra QA Backend — Architecture and Development Guide

## 1. Overview

Astra QA Backend is a platform for automated code testing with AI LLM agents. It orchestrates test execution across distributed workers, classifies failures using a LangGraph-based AI workflow, and provides real-time updates via WebSocket.

### Tech Stack

| Component | Technology |
|-----------|------------|
| Web Framework | Litestar 2.21.x |
| Language | Python 3.12+ |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 + pgvector |
| Cache / PubSub | Redis 7 |
| Task Queue | RabbitMQ + Taskiq |
| Object Storage | MinIO (S3-compatible) |
| Search | OpenSearch |
| AI / LLM | GigaChat Lite via LangGraph |
| Vector Search | pgvector (cosine similarity) |
| Migrations | Alembic (async) |
| Package Manager | UV |
| Container Runtime | Docker / Docker Compose |

### High-Level Architecture

```
                                ┌─────────────────────────────────────────────────────────────┐
                                │                     Clients (Browser / CI)                  │
                                └──────────────────────────────┬──────────────────────────────┘
                                                               │ HTTP/WebSocket
                                                               ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         Astra QA Backend (Litestar)                                    │
│                                                                                                         │
│  ┌──────────┐   ┌───────────────┐   ┌────────────────┐   ┌───────────────┐   ┌────────────────────┐  │
│  │ Health   │   │ Auth (OIDC)   │   │ Controllers    │   │  Services     │   │  Schemas (msgspec) │  │
│  │ /health  │   │ /auth/login   │   │ /api/v1/...   │   │ orchestrate   │   │  Request/Response  │  │
│  └──────────┘   │ /auth/callback│   │               │   │ ai_analyze    │   │  DTOs              │  │
│                 └───────────────┘   └────────┬───────┘   │ embeddings   │   └────────────────────┘  │
│                                               │          │ analytics    │                            │
│                                               ▼          └──────┬───────┘                            │
│                                        ┌──────────────────────┴──────────────────────────────┐        │
│                                        │               Repository Layer                        │        │
│                                        └──────────────────────┬──────────────────────────────┘        │
│                                                               │                                        │
└───────────────────────────────────────────────────────────────┼────────────────────────────────────────┘
                                                                │
          ┌─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────┐
          │                                                     │                                                     │
          ▼                                                     ▼                                                     ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   PostgreSQL        │    │   RabbitMQ           │    │   Redis              │    │   MinIO / S3         │
│   + pgvector        │    │   (Taskiq broker)    │    │   (Cache/Queue)      │    │   (Attachments)      │
│   (Main data store) │    │                      │    │                      │    │                      │
└─────────────────────┘    └──────────┬──────────┘    └─────────────────────┘    └─────────────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────────┐
                         │       Worker Process          │
                         │   (worker/run_shard.py)       │
                         │                               │
                         │  - Consumes RabbitMQ messages  │
                         │  - Runs pytest per shard      │
                         │  - Parses JUnit XML            │
                         │  - POSTs results to API        │
                         │  - Triggers AI analysis        │
                         └─────────────────────────────┘
```

## 2. Project Structure

```
astra_ai_qa_backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # Litestar app factory, route registration, WebSocket handler
│   ├── config.py            # pydantic-settings Settings (env vars with APP_ prefix)
│   ├── db.py                # async SQLAlchemy engine, session factory, plugin
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── sso.py           # OIDC SSO guard, login handler, callback handler, JWT validation
│   │   └── rbac.py          # RBAC guard, role-based route protection
│   ├── controllers/         # Litestar route handlers (API endpoints)
│   │   ├── __init__.py
│   │   ├── admin.py         # Settings, user management
│   │   ├── analytics.py     # DORA metrics, flaky test detection
│   │   ├── deploy.py        # Deployment triggers (preprod/prod approval)
│   │   ├── defects.py       # CRUD for defects
│   │   ├── imports.py       # JUnit XML import, CSV import
│   │   ├── projects.py      # Project CRUD
│   │   ├── scheduler.py     # Schedule management (cron expressions stored in DB)
│   │   ├── search.py        # OpenSearch integration
│   │   ├── test_cases.py    # Test case CRUD
│   │   ├── test_runs.py     # Test run creation, result submission, rerun
│   │   ├── test_suites.py   # Test suite CRUD
│   │   ├── metrics.py       # Prometheus-compatible metrics endpoint
│   │   └── webhooks.py      # Webhook handlers for external triggers
│   ├── services/            # Business logic layer
│   │   ├── __init__.py
│   │   ├── orchestration.py # Test run creation, LPT sharding, task scheduling
│   │   ├── ai_analyzer.py   # LangGraph-based failure classification service
│   │   ├── ai_workflow.py   # LangGraph StateGraph definition (4 nodes)
│   │   ├── analytics.py     # DORA metrics calculation, flaky test detection
│   │   ├── embeddings.py    # GigaChat embeddings (768-dim, cached)
│   │   ├── ws_manager.py    # In-memory WebSocket connection manager (singleton)
│   │   ├── notifications.py # Notification service (stub, None backend)
│   │   ├── backup.py        # Backup service (stub)
│   │   ├── report_generator.py  # PDF report generation via WeasyPrint/Jinja2
│   │   ├── scheduler.py     # Scheduler service (stub, cron expressions only)
│   │   ├── storage.py       # MinIO/S3 attachment storage
│   │   ├── search.py        # OpenSearch indexing and search
│   │   ├── jira_integration.py   # Jira issue creation/sync
│   │   ├── jira_sync.py     # Jira sync worker
│   │   ├── deploy.py        # Deployment logic
│   │   ├── registry.py      # Test registry
│   │   ├── sanitizer.py     # Input sanitization
│   │   ├── import_service.py   # JUnit/CSV import logic
│   │   └── test_case_generator.py   # AI-driven test case generation
│   ├── repositories/       # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── test_runs.py     # TestRun persistence and queries
│   │   └── ai.py            # AIAnalysis persistence, pgvector nearest-neighbor search
│   ├── models/              # SQLAlchemy ORM entities
│   │   ├── __init__.py
│   │   ├── base.py          # Declarative base
│   │   └── entities.py      # All entity classes (11 tables)
│   ├── schemas/             # msgspec Struct DTOs (request/response)
│   │   ├── __init__.py
│   │   └── schemas.py       # All Struct definitions
│   └── tasks/               # Taskiq task definitions
│       ├── __init__.py
│       ├── broker.py         # Taskiq broker configuration (RabbitMQ)
│       └── tasks.py         # run_suite_shard, analyze_run_failures tasks
│
├── worker/
│   ├── __init__.py
│   └── run_shard.py         # Standalone Python process, consumes RabbitMQ, runs pytest
│
├── alembic/
│   ├── env.py               # Async Alembic environment
│   ├── README
│   ├── script.py.mako
│   └── versions/            # Migration scripts
│       ├── 001_initial_tables.py
│       └── 002_add_requirement_id.py
│
├── tests/                   # pytest + pytest-asyncio tests
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_*.py            # ~30 test files covering services, endpoints, models
│
├── docs/
│   └── developer/
│       └── ARCHITECTURE.md   # This document
│
├── pyproject.toml           # Project dependencies (UV)
├── docker-compose.yml       # Local dev infrastructure (postgres, redis, rabbitmq, api)
├── Dockerfile              # Multi-stage build for production
└── .env.example             # Environment variable template
```

## 3. Data Model

**13 Tables:**

```
users (1) ←───────────────────────────── (N) projects
  │                                           │
  │ owned_projects                      test_suites
  │                                           │
users (1) ←───────────────────────────── (N) test_runs
  │                                           │
  │ triggered_by                         test_cases
  │                                           │
  │                                      test_results ←─ ai_analyses (1:1, optional)
  │                                           │
  │                                      attachments (1:N)
  │                                           │
  │                        defect_results (N:N)        │
  │                              ↕                    │
  │                          defects ←────────────────┘

test_cases (N) ←─────────────────────── (1) requirements (optional)
test_suites (1) ←─────────────────────── (N) schedules
```

**Entity Summary:**

| Table | Description |
|-------|-------------|
| `roles` | RBAC roles (id, code, description) |
| `users` | Users (email, full_name, role_id, ldap_dn, is_active) |
| `projects` | Projects (code, name, owner_id) |
| `test_suites` | Test suites (project_id, name, kind, config JSON) |
| `schedules` | Cron schedules (suite_id, cron_expression, timezone, is_active) |
| `requirements` | Requirements (title, source, external_id) |
| `test_cases` | Test cases (suite_id, title, source, code_path, avg_duration_ms, requirement_id) |
| `test_runs` | Test runs (suite_id, commit_sha, branch, priority, status, environment) |
| `test_results` | Individual test results (run_id, test_case_id, status, duration_ms, error_message, stack_trace, stdout, stderr) |
| `attachments` | File attachments for results (result_id, file_path, mime_type, size) |
| `ai_analyses` | AI failure analysis (result_id, category, probability, short_cause, suggestion, llm_model, prompt_hash, error_embedding VECTOR(768)) |
| `defects` | Defect records (title, description, severity, status, jira_key) |
| `defect_results` | M2M between defects and test_results |

**Key Indexes:**
- `ix_test_runs_suite_started` on (suite_id, started_at)
- `ix_test_runs_commit` on (commit_sha)
- `ix_test_results_run_status` on (run_id, status)
- `ix_test_results_finished` BRIN index on (finished_at)
- `ix_ai_analyses_vec` IVFFlat index on (error_embedding) with cosine_ops

## 4. Service Layer Architecture

### OrchestrationService (`app/services/orchestration.py`)

Responsible for the full lifecycle of a test run.

1. **create_run**: Creates a TestRun record, splits test cases into shards using LPT algorithm, schedules each shard via Taskiq.
2. **_split_by_lpt**: Longest Processing Time first — sorts cases by avg_duration_ms descending, then distributes round-robin to minimize shard variance.
3. **handle_result**: Persists TestResult records from worker callback, recomputes run status.
4. **_recompute_run_status**: Aggregates all result statuses. If all passed → passed. If any failed → failed. Otherwise remains running.
5. **rerun_failed**: Creates a new run with only the failed test cases from the original run.
6. **Task bus**: Uses TaskiqAdapter (real) or MockTaskBus (fallback when RabbitMQ is unavailable).

### AIAnalyzerService (`app/services/ai_analyzer.py`)

Wraps a LangGraph workflow to classify test failures.

- **Failure categories**: real_defect, flaky, infrastructure
- **Workflow**: Invokes EmbeddingService → AIRepository (duplicate check with cosine similarity > 0.92 threshold) → LLM classification via GigaChat → stores result.
- **Retry logic**: Up to 3 retries with exponential backoff for LLM calls.
- **Prompt**: Russian-language QA engineer persona prompt.

### AIWorkflowService (`app/services/ai_workflow.py`)

LangGraph StateGraph with 4 nodes and conditional routing:

```
START → compute_embedding → check_duplicate
                                   │
                         ┌─────────┴─────────┐
                         │                   │
                      [found]            [not found]
                         │                   │
                         ▼                   ▼
                        END          classify_failure
                                          │
                                          ▼
                                   build_recommendation
                                          │
                                          ▼
                                         END
```

- **compute_embedding**: Calls EmbeddingService.encode()
- **check_duplicate**: Calls AIRepository.find_nearest(), uses cosine similarity threshold of 0.92
- **classify_failure**: Sends error text + stack trace to GigaChat LLM with structured output (category, probability, short_cause, next_steps)
- **build_recommendation**: Computes SHA256 hash of prompt, sets LLM model name from settings

### AnalyticsService (`app/services/analytics.py`)

Calculates DORA metrics and detects flaky tests.

**DORA Metrics (calculate_dora):**
- **Lead Time**: Average time from started_at to finished_at for completed runs
- **Deployment Frequency**: Count of passed runs per day
- **Change Failure Rate**: Percentage of runs that failed
- **MTTR**: Average duration of failed runs

**Flaky Test Detection (detect_flaky_tests):**
- Groups results by test_case_id, ordered by finished_at descending
- Counts status transitions in last N results (default lookback=30, threshold=3)
- Flaky score = transitions / (total_runs - 1)

### EmbeddingsService (`app/services/embeddings.py`)

- Wrapper around GigaChat embeddings API
- 768-dimensional vectors stored in pgvector
- LRU cache (max 1000 entries) with move-to-end eviction
- Thread-based sync call wrapped in asyncio.to_thread

## 5. Authentication and Authorization

### OIDC SSO Flow

```
1. GET /api/v1/auth/login
   └─> Redirects to IdP (e.g., Indid at indid.astracr.ru)

2. User authenticates at IdP

3. IdP redirects to GET /api/v1/auth/callback?code=...
   └─> Backend exchanges code for tokens (access_token, id_token, refresh_token)
   └─> Validates id_token JWT against IdP's JWKS endpoint
   └─> Returns JWT access token to client

4. Client sends subsequent requests:
   Authorization: Bearer <jwt_access_token>

5. sso_auth_guard validates JWT on every request (except health, login, callback)
   - Verifies signature against IdP's public key (cached)
   - Checks audience and issuer
   - Extracts roles from realm_access.roles
```

In **debug mode** (APP_DEBUG=true), a synthetic AuthenticatedUser with admin role is injected automatically.

### RBAC Roles

| Role | Permissions |
|------|-------------|
| viewer | Read-only access to projects, suites, runs |
| qa_engineer | viewer + create runs, submit results, create defects |
| qa_lead | qa_engineer + create test cases, manage suites |
| admin | qa_lead + manage users, settings, admin endpoints |

Roles are enforced via `RBACGuard` / `require_role()` decorators on route handlers.

## 6. Configuration

All settings are in `app/config.py` via pydantic-settings with `APP_` prefix. Environment variables are loaded from `.env` file.

```bash
# Application
APP_SERVICE_NAME=astra-qa-backend
APP_HOST=0.0.0.0
APP_PORT=8000
APP_DEBUG=false
APP_LOG_LEVEL=INFO

# Database
APP_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/astra_qa

# Redis
APP_REDIS_URL=redis://localhost:6379/0

# RabbitMQ
APP_RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# CORS
APP_CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# OIDC / SSO
APP_OIDC_ISSUER_URL=https://sso.example.com/realms/astra
APP_OIDC_CLIENT_ID=astra-qa-backend
APP_OIDC_CLIENT_SECRET=your-client-secret-here

# LLM (GigaChat)
APP_LLM_PROVIDER=gigachat
APP_LLM_API_KEY=your-gigachat-api-key-here
APP_LLM_MODEL_NAME=GigaChat:latest
APP_LLM_TEMPERATURE=0.1
APP_LLM_MAX_TOKENS=8192

# MinIO / S3
APP_MINIO_ENDPOINT=localhost:9000
APP_MINIO_ACCESS_KEY=minioadmin
APP_MINIO_SECRET_KEY=minioadmin
APP_MINIO_SECURE=false

# Jira (optional)
APP_JIRA_BASE_URL=https://jira.astracr.ru
APP_JIRA_TOKEN=your-jira-token

# GitLab (optional)
APP_GITLAB_BASE_URL=https://gitlab.astracr.ru
APP_GITLAB_TOKEN=your-gitlab-token

# OpenSearch (optional)
APP_OPENSEARCH_URL=http://localhost:9200
```

## 7. WebSocket Real-Time Updates

**Endpoint**: `WS /api/v1/ws/runs/{run_id}`

Clients subscribe to a specific test run and receive real-time status updates.

```javascript
// Client subscribes
const ws = new WebSocket("ws://localhost:8000/api/v1/ws/runs/abc123");

// Message format from server
{
  "event": "status_change",   // or "result_added", "analysis_complete"
  "run_id": "abc123",
  "status": "running",         // pending, running, passed, failed
  "timestamp": "2026-04-28T12:00:00Z"
}
```

**Implementation**: `app/services/ws_manager.py` is an in-memory singleton. The `ConnectionManager` maps run_id to a list of asyncio.Queue instances. Call `await ws_manager.broadcast(run_id, message)` from the orchestration service when run status changes.

## 8. Worker Architecture

**`worker/run_shard.py`** — standalone Python process (no Litestar, no SQLAlchemy app context):

1. Connects to RabbitMQ via aio_pika
2. Declares durable queue (name from `TASKIQ_QUEUE_NAME` env, default "taskiq")
3. Consumes messages: `{run_id, shard_index, test_case_ids}`
4. For each shard:
   - Runs `pytest -v --junitxml=/tmp/shard_<run>_<index>.xml <test_case_ids>`
   - Parses JUnit XML output
   - POSTs results to `POST /api/v1/runs/{run_id}/results`
   - If any failed: calls `POST /api/v1/runs/{run_id}/analyses` to trigger AI analysis
5. Cleans up report file
6. Acknowledges message to RabbitMQ

**Run command**: `python -m worker.run_shard`

**Environment variables**:
- `RABBITMQ_URL` — RabbitMQ connection string
- `TASKIQ_QUEUE_NAME` — queue to consume from
- `ASTRA_API_URL` — backend API base URL (default http://localhost:8000/api/v1)

## 9. Database Migrations

Alembic with async SQLAlchemy engine.

```bash
# Generate a new migration
uv run alembic revision --autogenerate -m "description of change"

# Apply all pending migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# Check current version
uv run alembic current

# Show migration history
uv run alembic history
```

Migrations use `async_engine` from `app.db` via `alembic/env.py`.

## 10. Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_runs.py -v

# Run tests with coverage
uv run pytest tests/ --cov=app --cov-report=html

# Run only tests matching a name
uv run pytest tests/ -k "analytics"

# Run only async tests
uv run pytest tests/ -v --asyncio-mode=auto
```

Test configuration in `pyproject.toml`:
- `asyncio_mode = "auto"` with `asyncio_default_fixture_loop_scope = "function"`
- Test path: `tests/`

## 11. Docker / Deployment

```bash
# Start full local dev environment
docker-compose up -d

# Build production image
docker build -t astra-qa-backend:latest .

# Run production container with env file
docker run --env-file .env -p 8000:8000 astra-qa-backend:latest

# Run worker (separate container or process)
python -m worker.run_shard
```

**docker-compose.yml** includes: postgres (pgvector), redis, rabbitmq (management plugin on 15672), and the API service.

## 12. Development Workflow

```bash
# 1. Clone repository
git clone <repo_url>
cd astra_ai_qa_backend

# 2. Create environment file
cp .env.example .env
# Fill in required values: APP_DATABASE_URL, APP_LLM_API_KEY, APP_OIDC_*

# 3. Install dependencies
uv sync

# 4. Run database migrations
uv run alembic upgrade head

# 5. Start development server (hot reload)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. Run tests
uv run pytest tests/ -v

# 7. (Optional) Start worker for task processing
python -m worker.run_shard
```

## 13. Key Implementation Details

- **No Pydantic for DTOs** — all request/response objects use msgspec.Struct. Settings (config.py) do use Pydantic BaseSettings.
- **No sync SQLAlchemy** — everything is async with asyncpg driver. Session injection via Litestar's dependency injection (Provide).
- **No Celery** — Taskiq for async task distribution via RabbitMQ. Task definitions in `app/tasks/tasks.py`.
- **No Redis pub/sub** — in-memory asyncio Queue-based WebSocket manager (singleton). Redis is used for caching and as a message broker for Taskiq.
- **LangGraph for AI workflow** — 4-node StateGraph with conditional edges for duplicate detection routing.
- **pgvector for embeddings** — 768-dimensional vectors with cosine similarity. Threshold 0.92 for duplicate detection.
- **LPT sharding** — Longest Processing Time first algorithm for distributing test cases across workers to balance workload.

## 14. Known Limitations / TODOs

- **GOST signing** — stub implementation requires CryptoPro CSP. Not functional.
- **Scheduler** — cron expressions stored in DB but scheduler doesn't actually execute jobs. Workers poll or rely on external cron.
- **Backup service** — stub implementation, not functional.
- **Parquet export** — returns HTTP 501. Requires pandas + pyarrow integration.
- **OpenSearch integration** — configured but search service is basic.
- **Jira sync** — limited functionality, depends on valid Jira credentials and network access.
- **Test case generator** — AI-generated test cases from user stories, functional but depends on LLM availability.
- **Deployment approval flow** — preprod/prod gates exist but approval mechanism is minimal.