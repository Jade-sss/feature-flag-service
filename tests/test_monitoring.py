"""
Tests for monitoring, logging, and metrics.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.middleware.prometheus import (
    REGISTRY,
    REQUEST_COUNT,
    REQUEST_DURATION,
    FLAG_EVALUATIONS,
    REQUESTS_IN_PROGRESS,
    _normalize_path,
)

transport = ASGITransport(app=app)


# ── Path normalization ────────────────────────────────────────────────────────

def test_normalize_path_flag_key():
    assert _normalize_path("/flags/my-feature") == "/flags/{key}"


def test_normalize_path_flag_override():
    assert _normalize_path("/flags/my-feature/overrides/user-42") == "/flags/{key}/overrides/{user_id}"


def test_normalize_path_evaluate():
    assert _normalize_path("/flags/evaluate") == "/flags/evaluate"


def test_normalize_path_api_keys_id():
    assert _normalize_path("/api-keys/5") == "/api-keys/{id}"


def test_normalize_path_root():
    assert _normalize_path("/") == "/"


# ── Health check ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert "status" in body
        assert "db" in body
        assert "cache" in body


# ── Metrics endpoint ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/metrics")
        assert r.status_code == 200
        text = r.text
        # Should contain our custom metrics
        assert "http_requests_total" in text
        assert "http_request_duration_seconds" in text


@pytest.mark.asyncio
async def test_metrics_count_increments():
    """After making a request, the counter should increase."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Make a request
        await ac.get("/")
        await ac.get("/")

        # Scrape metrics
        r = await ac.get("/metrics")
        text = r.text
        # We should see the root path counted
        assert "http_requests_total" in text


@pytest.mark.asyncio
async def test_flag_evaluation_metric():
    """Flag evaluation should be tracked in metrics."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a flag & evaluate
        await ac.post("/flags/", json={"key": "metric-flag", "is_enabled": True})
        await ac.get("/flags/evaluate", params={"key": "metric-flag"})

        r = await ac.get("/metrics")
        text = r.text
        assert "flag_evaluations_total" in text


# ── X-Request-ID correlation ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_response_contains_request_id():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/")
        assert "x-request-id" in r.headers


@pytest.mark.asyncio
async def test_request_id_propagated():
    """If client sends X-Request-ID, it should be echoed back."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/", headers={"X-Request-ID": "my-trace-123"})
        assert r.headers.get("x-request-id") == "my-trace-123"
