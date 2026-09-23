import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.core.config import settings
from app.db import get_database
from app.main import app
from app.repositories import (
    announcement_repository,
    movie_repository,
    reservation_repository,
    screening_repository,
    screening_request_repository,
    tag_repository,
    tv_show_repository,
    user_repository,
    visit_repository,
)


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
    monkeypatch.setattr(settings, "discogs_token", "")
    monkeypatch.setattr(settings, "upcdatabase_token", "")
    monkeypatch.setattr(settings, "ean_search_api_key", "")
    monkeypatch.setattr(settings, "omdb_api_key", "")
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")


@pytest.fixture(autouse=True)
def _pin_password_policy(monkeypatch):
    """Feature #174 — same isolation concern as `_pin_external_api_keys`
    above, but sharper: `settings.password_*` is read on *every* password
    set anywhere (registration, self-change, admin-reset generation), so an
    override left over from one test (e.g. `password_require_uppercase =
    True`) would silently break registration — and therefore the `client`
    fixture itself — in every test file that happens to run afterward.
    Pinned to the code defaults (matching `Settings`' own) so a test that
    never touches the policy behaves exactly as if the feature didn't
    exist."""
    monkeypatch.setattr(settings, "password_min_length", 8)
    monkeypatch.setattr(settings, "password_require_uppercase", False)
    monkeypatch.setattr(settings, "password_require_lowercase", False)
    monkeypatch.setattr(settings, "password_require_digit", False)


@pytest.fixture(autouse=True)
def _pin_screening_request_policy(monkeypatch):
    """Feature #177/#186 — same isolation concern as `_pin_password_policy`
    above: pinned to the code default (`True`) so a test that turns it off
    doesn't leak into every other screening-request test that runs
    afterward."""
    monkeypatch.setattr(settings, "require_preferred_at", True)


@pytest.fixture(autouse=True)
def _pin_plex_auto_import_policy(monkeypatch):
    """Feature #181/#182 — same isolation concern as `_pin_password_policy`
    above. `plex_import_tag` in particular is now mutated by `import_from_plex`
    itself (not just the PATCH endpoint) whenever a non-dry-run import runs
    with a real (non-auto-scan) actor — without this pin, any test in
    `test_plex.py` that imports with a custom tag would leak that tag into
    every test running afterward, in any file, for the rest of the process."""
    monkeypatch.setattr(settings, "plex_auto_import_enabled", False)
    monkeypatch.setattr(settings, "plex_auto_import_interval_minutes", 360)
    monkeypatch.setattr(settings, "plex_import_tag", "Plex-import")


@pytest.fixture(autouse=True)
def _pin_test_mode(monkeypatch):
    """Feature #217 — same isolation concern as `_pin_password_policy`
    above: pinned to the code default (`False`) so a test that turns test
    mode on doesn't silently swallow every message/email assertion in every
    other test file that happens to run afterward in the same process."""
    monkeypatch.setattr(settings, "test_mode", False)


@pytest.fixture(autouse=True)
def _reset_anthem_session_state(monkeypatch):
    """Feature #183 — `anthem_service._session_active` is a plain module
    global (see its own docstring for why it's a bool, not an
    `asyncio.Lock`), so without this pin a test that leaves a diagnostic
    "session" active (e.g. by raising before reaching the generator's
    `finally`) would permanently lock every later test out with a 409,
    across the whole file and beyond — same isolation concern as
    `_pin_plex_auto_import_policy` above."""
    from app.services import anthem_service

    monkeypatch.setattr(anthem_service, "_session_active", False)


@pytest_asyncio.fixture
async def db():
    test_db = AsyncMongoMockClient()["test_moviedb"]
    await movie_repository.ensure_indexes(test_db)
    await tv_show_repository.ensure_indexes(test_db)
    await tag_repository.ensure_indexes(test_db)
    await user_repository.ensure_indexes(test_db)
    await screening_request_repository.ensure_indexes(test_db)
    await screening_repository.ensure_indexes(test_db)
    await visit_repository.ensure_indexes(test_db)
    await reservation_repository.ensure_indexes(test_db)
    await announcement_repository.ensure_indexes(test_db)
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
