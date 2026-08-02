import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.core.config import settings
from app.db import get_database
from app.main import app
from app.repositories import movie_repository, tag_repository, tv_show_repository, user_repository


@pytest.fixture(autouse=True)
def _pin_external_api_keys(monkeypatch):
    """The test suite must never depend on the developer's local `.env`
    (BUGS.md #31): `Settings.env_file=".env"` resolves relative to the
    current working directory, so `pytest` run from `backend/` was silently
    picking up Jan's real TMDb token — masking that `sync_all_from_tmdb`'s
    tests fail the moment `pytest` runs from anywhere else (e.g. the repo
    root), and would fail identically in CI, where no `.env` exists at all.

    Every test now gets a fixed, obviously-fake set of keys instead of
    whatever the environment happens to provide. `tmdb_api_token` is
    non-empty because tests that exercise `sync_all_from_tmdb`'s "token
    missing" short-circuit are the whole point of BUGS.md #15/#16 and need
    it truthy by default (they set it back to "" themselves). The others
    stay empty/falsy — most creation/sync tests never mock
    `omdb_client`/`plex_client` at all and rely on their real, unmocked
    "no key configured" fallback to avoid making a genuine network call."""
    monkeypatch.setattr(settings, "tmdb_api_token", "test-tmdb-token")
    monkeypatch.setattr(settings, "upc_api_key", "")
    monkeypatch.setattr(settings, "discogs_token", "")
    monkeypatch.setattr(settings, "omdb_api_key", "")
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")


@pytest_asyncio.fixture
async def db():
    test_db = AsyncMongoMockClient()["test_moviedb"]
    await movie_repository.ensure_indexes(test_db)
    await tv_show_repository.ensure_indexes(test_db)
    await tag_repository.ensure_indexes(test_db)
    await user_repository.ensure_indexes(test_db)
    return test_db


@pytest_asyncio.fixture
async def raw_client(db):
    """AsyncClient with no logged-in user — for testing auth gating itself."""
    app.dependency_overrides[get_database] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(raw_client):
    """AsyncClient logged in as a default test user (cookie persists via httpx's jar)."""
    await raw_client.post(
        "/api/auth/register", json={"username": "testuser", "password": "testpassword123"}
    )
    yield raw_client
