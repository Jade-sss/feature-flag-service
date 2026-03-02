# Feature Flag Service

A production-ready REST API for managing feature flags, built with **Python 3.12** and **FastAPI**.

The service stores feature flags with metadata, manages flag states globally and per-user, evaluates feature availability in real time, and uses Redis caching for performance.

---

## Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Caching Strategy](#caching-strategy)
- [Testing](#testing)
- [CI/CD](#cicd)
- [Observability](#observability)

---

## Architecture

The full request lifecycle, evaluation flow, and data model are documented with Mermaid diagrams in **[docs/architecture.md](docs/architecture.md)**.

**High-level summary:**

```
Client → CORS → TrustedHost → Prometheus → RateLimiter → SecurityHeaders → RequestLogger
  → FastAPI Router → Auth (X-API-Key) → Handler → Repository → DB / Cache
```

Every request passes through six middleware layers before reaching the application. The evaluation engine checks the cache first, falls back to the database, and caches the result for subsequent calls.

---

## Features

| Capability | Details |
|---|---|
| **Flag CRUD** | Create, read, update, delete feature flags |
| **Per-user overrides** | Enable/disable flags for specific users |
| **Evaluation engine** | Global toggle → per-user override → percentage rollout (SHA-1 hash) |
| **Redis caching** | Flag data (5 min TTL) + evaluation results (1 min TTL), graceful degradation |
| **API key auth** | SHA-256 hashed keys, admin/readonly roles, master key bootstrap |
| **Rate limiting** | Sliding-window per IP (Redis-backed, in-memory fallback) |
| **Security headers** | CSP, HSTS, X-Frame-Options, X-Content-Type-Options, etc. |
| **Prometheus metrics** | Request count/duration/in-progress, flag evaluations, cache hit/miss |
| **Structured logging** | JSON or text format, X-Request-ID correlation |
| **Input validation** | Pydantic v2 schemas with regex patterns, length limits, range constraints |
| **Health checks** | `GET /` (shallow) and `GET /health` (deep — verifies DB + Redis) |

---

## Tech Stack

| Component | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL (production) / SQLite (dev & test) |
| Cache | Redis ≥ 4.5 |
| Auth | API key via `X-API-Key` header |
| Metrics | prometheus-client |
| Logging | python-json-logger |
| Testing | pytest + pytest-asyncio + httpx |
| CI | GitHub Actions |

---

## Project Structure

```
feature_flag_service/
├── .github/workflows/ci.yml    # CI pipeline
├── docs/architecture.md         # Architecture diagrams (Mermaid)
├── src/app/
│   ├── main.py                  # FastAPI app, lifespan, middleware stack
│   ├── api/
│   │   ├── deps.py              # Auth dependencies (require_any_key, require_admin)
│   │   └── routers/
│   │       ├── flags.py         # Flag CRUD + evaluation + override endpoints
│   │       └── api_keys.py      # API key management endpoints
│   ├── cache/
│   │   └── redis_cache.py       # Redis caching with graceful degradation
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   ├── exceptions.py        # Global exception handlers
│   │   └── logging_config.py    # Structured logging setup
│   ├── db/
│   │   ├── base.py              # SQLAlchemy Base
│   │   ├── session.py           # Engine, session factory, pool config
│   │   ├── models/
│   │   │   ├── feature_flag.py  # FeatureFlag + FlagOverride models
│   │   │   └── api_key.py       # APIKey model (SHA-256 hashed)
│   │   └── repositories/
│   │       ├── flag_repository.py
│   │       └── api_key_repository.py
│   ├── middleware/
│   │   ├── prometheus.py        # Metrics collection + /metrics endpoint
│   │   ├── rate_limit.py        # Sliding-window rate limiter
│   │   ├── request_logging.py   # Access log + X-Request-ID
│   │   └── security_headers.py  # Security response headers
│   ├── schemas/
│   │   ├── flag.py              # Pydantic request/response models
│   │   └── api_key.py           # API key schemas
│   └── services/
│       └── evaluator.py         # Flag evaluation logic + rollout
├── tests/
│   ├── conftest.py              # Test DB, fixtures, dependency overrides
│   ├── test_api.py              # 14 functional tests (CRUD + evaluation)
│   ├── test_auth.py             # 14 auth & rate limiting tests
│   ├── test_hardening.py        # 12 security & validation tests
│   └── test_monitoring.py       # 11 observability tests
├── .env.example                 # All environment variables documented
├── requirements.txt
├── pytest.ini
└── alembic.ini                  # Database migrations (Alembic)
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Redis (optional — service degrades gracefully without it)
- PostgreSQL (or use SQLite for local dev)

### 1. Clone & install

```bash
git clone https://github.com/Jade-sss/feature-flag-service.git
cd feature-flag-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — at minimum set:
#   DATABASE_URL=sqlite+aiosqlite:///./featureflags.db
#   AUTH_ENABLED=false            # for local dev
```

### 3. Run

```bash
PYTHONPATH=src uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 4. Quick smoke test

```bash
# Create a flag
curl -s -X POST http://localhost:8000/flags/ \
  -H "Content-Type: application/json" \
  -d '{"key": "dark-mode", "description": "Dark mode toggle", "is_enabled": true}' | jq

# Evaluate
curl -s "http://localhost:8000/flags/evaluate?key=dark-mode&user_id=alice" | jq
```

---

## Configuration

All settings are loaded from environment variables (or a `.env` file). See [.env.example](.env.example) for the full list.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async DB connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `ENV` | `development` | `development` / `staging` / `production` |
| `AUTH_ENABLED` | `true` | Set `false` to disable auth for local dev |
| `MASTER_API_KEY` | *(none)* | Bootstrap admin key (set a strong secret) |
| `RATE_LIMIT_REQUESTS` | `100` | Max requests per window per IP |
| `RATE_LIMIT_WINDOW` | `60` | Sliding window in seconds |
| `LOG_FORMAT` | `text` | `text` or `json` (use `json` in production) |
| `CORS_ORIGINS` | `*` | Comma-separated origins |
| `DB_POOL_SIZE` | `10` | Connection pool size |
| `DB_POOL_MAX_OVERFLOW` | `20` | Max overflow connections |
| `DB_POOL_RECYCLE` | `3600` | Recycle connections after N seconds |

---

## API Reference

### Feature Flags

| Method | Path | Auth | Status | Description |
|---|---|---|---|---|
| `POST` | `/flags/` | admin | 201 | Create a flag |
| `GET` | `/flags/` | any | 200 | List all flags |
| `GET` | `/flags/{key}` | any | 200 | Get flag by key |
| `PATCH` | `/flags/{key}` | admin | 200 | Update a flag |
| `DELETE` | `/flags/{key}` | admin | 204 | Delete a flag |
| `GET` | `/flags/evaluate?key=...&user_id=...` | any | 200 | Evaluate flag |

### Per-user Overrides

| Method | Path | Auth | Status | Description |
|---|---|---|---|---|
| `GET` | `/flags/{key}/overrides` | admin | 200 | List overrides |
| `PUT` | `/flags/{key}/overrides/{user_id}` | admin | 200 | Set override |
| `DELETE` | `/flags/{key}/overrides/{user_id}` | admin | 204 | Remove override |

### API Keys

| Method | Path | Auth | Status | Description |
|---|---|---|---|---|
| `POST` | `/api-keys/` | admin | 201 | Create key (returns raw key once) |
| `GET` | `/api-keys/` | admin | 200 | List keys |
| `DELETE` | `/api-keys/{id}` | admin | 204 | Revoke key |

### Health & Observability

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | none | Shallow health check |
| `GET` | `/health` | none | Deep check (DB + Redis) |
| `GET` | `/metrics` | none | Prometheus metrics |

---

## Authentication

Requests are authenticated via the `X-API-Key` header. Two roles exist:

- **admin** — full access to all endpoints (CRUD, overrides, key management)
- **readonly** — can list/get flags and evaluate

**Bootstrap:** Set `MASTER_API_KEY` env var to get initial admin access, then use it to create database-backed keys via `POST /api-keys/`.

**Local dev:** Set `AUTH_ENABLED=false` to bypass auth entirely.

```bash
# Create a readonly key
curl -s -X POST http://localhost:8000/api-keys/ \
  -H "X-API-Key: $MASTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "sdk-key", "role": "readonly"}' | jq

# Use the returned raw_key for subsequent requests
curl -s http://localhost:8000/flags/ -H "X-API-Key: <raw_key>"
```

---

## Rate Limiting

Every IP is tracked with a sliding-window counter (Redis sorted sets, in-memory fallback).

- **Default:** 100 requests per 60-second window
- **Response headers:** `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- **Exceeded:** `429 Too Many Requests` with `Retry-After` header
- **Exempted:** `GET /` health check

---

## Caching Strategy

| Cache Key | TTL | Invalidated On |
|---|---|---|
| `flag:{key}` | 300s (5 min) | Create / Update / Delete flag |
| `eval:{key}:{user_id}` | 60s (1 min) | Create / Update / Delete flag or override |

If Redis is unavailable, the service continues running (all cache calls gracefully degrade to no-ops).

---

## Testing

The test suite uses an **in-memory SQLite** database and requires no external services.

```bash
# Run all 51 tests
PYTHONPATH=src python -m pytest tests/ -v

# Run a specific test file
PYTHONPATH=src python -m pytest tests/test_auth.py -v

# Run with warnings-as-errors
PYTHONPATH=src python -m pytest tests/ -v -W error
```

**Test breakdown:**

| File | Tests | Coverage |
|---|---|---|
| `test_api.py` | 14 | Flag CRUD, evaluation, overrides, status codes |
| `test_auth.py` | 14 | API key auth, roles, revocation, rate limiting |
| `test_hardening.py` | 12 | Security headers, input validation, error format |
| `test_monitoring.py` | 11 | Metrics, health check, request ID, path normalization |
| **Total** | **51** | All passing, 0 warnings |

---

## CI/CD

GitHub Actions pipeline (`.github/workflows/ci.yml`) runs on every push and PR to `main`:

1. **Checkout** — `actions/checkout@v4`
2. **Python 3.12** — `actions/setup-python@v5` with pip cache
3. **Redis service** — Redis 7 Alpine with health checks
4. **Install deps** — `pip install -r requirements.txt`
5. **Lint** — `ruff check` (non-blocking)
6. **Test** — `pytest -v --tb=short -W error`
7. **Upload results** — `actions/upload-artifact@v4`

---

## Observability

### Structured Logging

- **Dev:** Human-readable text format with timestamps
- **Production:** JSON format (`LOG_FORMAT=json`) for log aggregation
- Every response includes `X-Request-ID` for correlation

### Prometheus Metrics

Available at `GET /metrics`:

| Metric | Type | Labels |
|---|---|---|
| `http_requests_total` | Counter | method, path_template, status_code |
| `http_request_duration_seconds` | Histogram | method, path_template |
| `http_requests_in_progress` | Gauge | — |
| `flag_evaluations_total` | Counter | result (true/false) |
| `cache_hits_total` | Counter | cache_type (flag/eval) |
| `cache_misses_total` | Counter | cache_type (flag/eval) |

### Health Checks

- `GET /` — shallow probe (always 200)
- `GET /health` — deep check (pings DB + Redis, returns `ok` or `degraded`)

---

## License

MIT
