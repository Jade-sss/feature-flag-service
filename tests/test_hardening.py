"""
Tests for production hardening:
  - Security headers
  - CORS
  - Input validation (schema constraints)
  - Global exception handler (validation errors return structured JSON)
  - Health check
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings

transport = ASGITransport(app=app)


# ── Security headers ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_security_headers_present():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/")
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"
        assert r.headers.get("x-xss-protection") == "1; mode=block"
        assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "default-src 'none'" in r.headers.get("content-security-policy", "")


@pytest.mark.asyncio
async def test_no_cache_headers_on_api():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/flags/")
        assert "no-store" in r.headers.get("cache-control", "")


@pytest.mark.asyncio
async def test_hsts_not_in_development():
    """HSTS should only be sent in production."""
    orig = settings.ENV
    settings.ENV = "development"
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/")
            assert "strict-transport-security" not in r.headers
    finally:
        settings.ENV = orig


# ── Input validation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_flag_key_rejects_empty():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/flags/", json={"key": ""})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_flag_key_rejects_special_chars():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/flags/", json={"key": "bad key!@#"})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_flag_key_accepts_valid_pattern():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/flags/", json={"key": "valid-flag.name_v2"})
        assert r.status_code == 201


@pytest.mark.asyncio
async def test_rollout_percentage_rejects_out_of_range():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/flags/", json={"key": "pct-flag", "rollout_percentage": 150})
        assert r.status_code == 422

        r = await ac.post("/flags/", json={"key": "pct-flag2", "rollout_percentage": -1})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_api_key_name_rejects_empty():
    """API key name must be at least 1 char."""
    settings.AUTH_ENABLED = True
    settings.MASTER_API_KEY = "test-master"
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api-keys/",
                json={"name": "", "role": "readonly"},
                headers={"X-API-Key": "test-master"},
            )
            assert r.status_code == 422
    finally:
        settings.AUTH_ENABLED = False
        settings.MASTER_API_KEY = None


@pytest.mark.asyncio
async def test_api_key_role_rejects_invalid():
    """API key role must be admin or readonly."""
    settings.AUTH_ENABLED = True
    settings.MASTER_API_KEY = "test-master"
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api-keys/",
                json={"name": "bad-role", "role": "superuser"},
                headers={"X-API-Key": "test-master"},
            )
            assert r.status_code == 422
    finally:
        settings.AUTH_ENABLED = False
        settings.MASTER_API_KEY = None


# ── Validation error format ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validation_error_structured():
    """Validation errors should return structured JSON with 'errors' array."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/flags/", json={"key": ""})
        assert r.status_code == 422
        body = r.json()
        assert "errors" in body
        assert isinstance(body["errors"], list)
        assert len(body["errors"]) > 0
        assert "field" in body["errors"][0]
        assert "message" in body["errors"][0]


# ── X-Request-ID still works with security headers ───────────────────────────

@pytest.mark.asyncio
async def test_request_id_with_security_headers():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/", headers={"X-Request-ID": "trace-abc"})
        assert r.headers.get("x-request-id") == "trace-abc"
        assert r.headers.get("x-content-type-options") == "nosniff"


# ── Health endpoint in hardened app ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_status():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("ok", "degraded")
