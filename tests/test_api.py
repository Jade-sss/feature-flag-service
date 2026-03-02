import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

transport = ASGITransport(app=app)


# ── Health check ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ── Requirement 1: Creation & Storage ─────────────────────────────────────

@pytest.mark.asyncio
async def test_create_flag_returns_201():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/flags/", json={
            "key": "new-feature",
            "description": "A brand-new feature",
            "is_enabled": False,
        })
        assert r.status_code == 201
        body = r.json()
        assert body["key"] == "new-feature"
        assert body["description"] == "A brand-new feature"
        assert body["is_enabled"] is False
        assert "id" in body


@pytest.mark.asyncio
async def test_create_duplicate_flag_returns_409():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/flags/", json={"key": "dup-flag"})
        r = await ac.post("/flags/", json={"key": "dup-flag"})
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_get_flag_returns_stored_data():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/flags/", json={
            "key": "stored-flag",
            "description": "persisted",
            "is_enabled": True,
        })
        r = await ac.get("/flags/stored-flag")
        assert r.status_code == 200
        assert r.json()["description"] == "persisted"
        assert r.json()["is_enabled"] is True


@pytest.mark.asyncio
async def test_list_flags():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/flags/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ── Requirement 2: Management (global + per-user) ────────────────────────

@pytest.mark.asyncio
async def test_toggle_flag_globally():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/flags/", json={"key": "toggle-me", "is_enabled": False})

        # enable globally
        r = await ac.patch("/flags/toggle-me", json={"is_enabled": True})
        assert r.status_code == 200
        assert r.json()["is_enabled"] is True

        # disable globally
        r = await ac.patch("/flags/toggle-me", json={"is_enabled": False})
        assert r.status_code == 200
        assert r.json()["is_enabled"] is False


@pytest.mark.asyncio
async def test_per_user_override():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/flags/", json={"key": "user-flag", "is_enabled": False})

        # set override for user-42
        r = await ac.put(
            "/flags/user-flag/overrides/user-42",
            json={"user_id": "user-42", "enabled": True},
        )
        assert r.status_code == 200
        assert r.json()["user_id"] == "user-42"
        assert r.json()["enabled"] is True

        # list overrides
        r = await ac.get("/flags/user-flag/overrides")
        assert r.status_code == 200
        assert len(r.json()) >= 1

        # delete override
        r = await ac.delete("/flags/user-flag/overrides/user-42")
        assert r.status_code == 204


# ── Requirement 3: Evaluation ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_globally_enabled():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/flags/", json={"key": "eval-global", "is_enabled": True})
        r = await ac.get("/flags/evaluate", params={"key": "eval-global"})
        assert r.status_code == 200
        assert r.json()["enabled"] is True


@pytest.mark.asyncio
async def test_evaluate_globally_disabled():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/flags/", json={"key": "eval-off", "is_enabled": False})
        r = await ac.get("/flags/evaluate", params={"key": "eval-off"})
        assert r.status_code == 200
        assert r.json()["enabled"] is False


@pytest.mark.asyncio
async def test_evaluate_with_user_override():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/flags/", json={"key": "eval-user", "is_enabled": False})
        await ac.put(
            "/flags/eval-user/overrides/alice",
            json={"user_id": "alice", "enabled": True},
        )
        r = await ac.get("/flags/evaluate", params={"key": "eval-user", "user_id": "alice"})
        assert r.status_code == 200
        assert r.json()["enabled"] is True


@pytest.mark.asyncio
async def test_evaluate_nonexistent_flag():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/flags/evaluate", params={"key": "does-not-exist"})
        assert r.status_code == 200
        assert r.json()["enabled"] is False


# ── Requirement 4: HTTP Status Codes ─────────────────────────────────────

@pytest.mark.asyncio
async def test_get_nonexistent_flag_404():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/flags/no-such-flag")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_flag_204():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/flags/", json={"key": "delete-me"})
        r = await ac.delete("/flags/delete-me")
        assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_nonexistent_flag_404():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.delete("/flags/ghost-flag")
        assert r.status_code == 404
