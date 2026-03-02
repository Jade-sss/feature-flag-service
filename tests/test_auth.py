"""
Tests for authentication (API key) and rate limiting.

These tests temporarily enable AUTH_ENABLED to exercise the auth layer,
then restore the original setting so they don't affect other test files.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.middleware.rate_limit import _mem_store

transport = ASGITransport(app=app)

ADMIN_MASTER = "test-master-key-for-ci"


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _enable_auth():
    """Enable auth + set master key for every test in this module."""
    orig_auth = settings.AUTH_ENABLED
    orig_master = settings.MASTER_API_KEY
    settings.AUTH_ENABLED = True
    settings.MASTER_API_KEY = ADMIN_MASTER
    yield
    settings.AUTH_ENABLED = orig_auth
    settings.MASTER_API_KEY = orig_master


@pytest.fixture(autouse=True)
def _clear_rate_limit_store():
    """Clear the in-memory rate-limit store between tests."""
    _mem_store.clear()
    yield
    _mem_store.clear()


def admin_headers():
    return {"X-API-Key": ADMIN_MASTER}


# ── Auth: missing / invalid key ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_api_key_returns_401():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/flags/")
        assert r.status_code == 401
        assert "Missing" in r.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_api_key_returns_401():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/flags/", headers={"X-API-Key": "bogus-key"})
        assert r.status_code == 401
        assert "Invalid" in r.json()["detail"]


# ── Auth: master key grants admin access ─────────────────────────────────────

@pytest.mark.asyncio
async def test_master_key_can_create_flag():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/flags/",
            json={"key": "auth-flag", "is_enabled": True},
            headers=admin_headers(),
        )
        assert r.status_code == 201
        assert r.json()["key"] == "auth-flag"


@pytest.mark.asyncio
async def test_master_key_can_list_flags():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/flags/", headers=admin_headers())
        assert r.status_code == 200


# ── Auth: API key CRUD ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_api_key():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api-keys/",
            json={"name": "ci-key", "role": "readonly"},
            headers=admin_headers(),
        )
        assert r.status_code == 201
        body = r.json()
        assert "raw_key" in body
        assert body["name"] == "ci-key"
        assert body["role"] == "readonly"
        assert body["is_active"] is True


@pytest.mark.asyncio
async def test_create_api_key_without_admin_returns_403():
    """A readonly key cannot create new keys."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First, create a readonly key using master
        cr = await ac.post(
            "/api-keys/",
            json={"name": "reader", "role": "readonly"},
            headers=admin_headers(),
        )
        readonly_key = cr.json()["raw_key"]

        # Now try to create another key with the readonly key
        r = await ac.post(
            "/api-keys/",
            json={"name": "hacker", "role": "admin"},
            headers={"X-API-Key": readonly_key},
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_api_keys():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api-keys/",
            json={"name": "list-test", "role": "readonly"},
            headers=admin_headers(),
        )
        r = await ac.get("/api-keys/", headers=admin_headers())
        assert r.status_code == 200
        assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_revoke_api_key():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        cr = await ac.post(
            "/api-keys/",
            json={"name": "revoke-me", "role": "readonly"},
            headers=admin_headers(),
        )
        key_id = cr.json()["id"]
        raw_key = cr.json()["raw_key"]

        # Key works before revocation
        r = await ac.get("/flags/", headers={"X-API-Key": raw_key})
        assert r.status_code == 200

        # Revoke
        r = await ac.delete(f"/api-keys/{key_id}", headers=admin_headers())
        assert r.status_code == 204

        # Key no longer works
        r = await ac.get("/flags/", headers={"X-API-Key": raw_key})
        assert r.status_code == 401


# ── Auth: role enforcement on flag routes ────────────────────────────────────

@pytest.mark.asyncio
async def test_readonly_key_can_read_and_evaluate():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a readonly key
        cr = await ac.post(
            "/api-keys/",
            json={"name": "reader2", "role": "readonly"},
            headers=admin_headers(),
        )
        ro_key = cr.json()["raw_key"]
        ro_headers = {"X-API-Key": ro_key}

        # Create a flag to read (using master)
        await ac.post(
            "/flags/",
            json={"key": "ro-flag", "is_enabled": True},
            headers=admin_headers(),
        )

        # Read endpoints work
        r = await ac.get("/flags/", headers=ro_headers)
        assert r.status_code == 200

        r = await ac.get("/flags/ro-flag", headers=ro_headers)
        assert r.status_code == 200

        r = await ac.get("/flags/evaluate", params={"key": "ro-flag"}, headers=ro_headers)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_readonly_key_cannot_mutate():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        cr = await ac.post(
            "/api-keys/",
            json={"name": "reader3", "role": "readonly"},
            headers=admin_headers(),
        )
        ro_key = cr.json()["raw_key"]
        ro_headers = {"X-API-Key": ro_key}

        # Create should fail with 403
        r = await ac.post(
            "/flags/",
            json={"key": "nope", "is_enabled": False},
            headers=ro_headers,
        )
        assert r.status_code == 403

        # Patch should fail
        r = await ac.patch(
            "/flags/some-flag",
            json={"is_enabled": True},
            headers=ro_headers,
        )
        assert r.status_code == 403

        # Delete should fail
        r = await ac.delete("/flags/some-flag", headers=ro_headers)
        assert r.status_code == 403


# ── Rate limiting ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_headers_present():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/flags/", headers=admin_headers())
        assert "x-ratelimit-limit" in r.headers
        assert "x-ratelimit-remaining" in r.headers
        assert "x-ratelimit-reset" in r.headers


@pytest.mark.asyncio
async def test_rate_limit_decrements():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.get("/flags/", headers=admin_headers())
        rem1 = int(r1.headers["x-ratelimit-remaining"])

        r2 = await ac.get("/flags/", headers=admin_headers())
        rem2 = int(r2.headers["x-ratelimit-remaining"])

        assert rem2 < rem1


@pytest.mark.asyncio
async def test_rate_limit_returns_429():
    """When the limit is exceeded, the server returns 429."""
    orig_limit = settings.RATE_LIMIT_REQUESTS
    settings.RATE_LIMIT_REQUESTS = 3  # very low limit for test
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(3):
                await ac.get("/flags/", headers=admin_headers())
            r = await ac.get("/flags/", headers=admin_headers())
            assert r.status_code == 429
            assert "Rate limit exceeded" in r.json()["detail"]
            assert "retry-after" in r.headers
    finally:
        settings.RATE_LIMIT_REQUESTS = orig_limit


@pytest.mark.asyncio
async def test_health_check_not_rate_limited():
    """The / endpoint is exempt from rate limiting."""
    orig_limit = settings.RATE_LIMIT_REQUESTS
    settings.RATE_LIMIT_REQUESTS = 2
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(5):
                r = await ac.get("/")
                assert r.status_code == 200
    finally:
        settings.RATE_LIMIT_REQUESTS = orig_limit
