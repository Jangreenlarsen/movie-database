"""Feature #178-opfølgning (Jan: "sæt op i users styring hvem kan se og
bruge vis iplex/spil i plex i detajle for film/tv") — pr.-bruger til/fra
for "Afspil i Plex"-linket (feature #45/#88), ikke rolle-baseret (Jans
eksplicitte valg). Kun selve linket er omfattet, ikke Plex-badget på kortet
eller "available"/"matched_by" i øvrigt.
"""

from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.integrations import plex_client
from app.main import app
from app.services import plex_service


def _fake_library(items):
    from app.integrations.plex_client import PlexFetchResult, PlexSectionResult

    return PlexFetchResult(
        ok=True,
        machine_identifier="abc123",
        sections=[PlexSectionResult(key="1", title="Film", type="movie", item_count=len(items))],
        items=items,
    )


def _patch_library(monkeypatch, items):
    from app.integrations.plex_client import PlexItem  # noqa: F401

    async def fake_fetch_library():
        return _fake_library(items)

    monkeypatch.setattr(plex_client, "fetch_library", fake_fetch_library)


def _configure(monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "http://192.168.1.50:32400")
    monkeypatch.setattr(settings, "plex_token", "tok")


async def _standard_client(admin_client, username):
    transport = ASGITransport(app=app)
    standard = AsyncClient(transport=transport, base_url="http://test")
    register = await standard.post(
        "/api/auth/register", json={"username": username, "password": "testpassword123"}
    )
    user_id = register.json()["id"]
    await admin_client.patch(f"/api/users/{user_id}/status", json={"status": "active"})
    await admin_client.patch(f"/api/users/{user_id}/role", json={"role": "standard"})
    return standard, user_id


async def test_new_users_default_to_plex_play_enabled(client):
    """Regel 16 — en helt ny restriktion på en hidtil ubegrænset feature må
    ikke stille og roligt fjerne adgang for eksisterende/nye konti; en admin
    skal slå den fra eksplicit, det er ikke en opt-in-liste."""
    response = await client.get("/api/users/me")
    assert response.json()["plex_play_enabled"] is True


async def test_updating_plex_play_requires_admin(client):
    standard, user_id = await _standard_client(client, "notadmin_plexplay")

    response = await standard.patch(f"/api/users/{user_id}/plex-play", json={"enabled": False})
    assert response.status_code == 403


async def test_admin_can_disable_and_reenable_plex_play_for_a_user(client):
    standard, user_id = await _standard_client(client, "plexplaytoggle")

    disable = await client.patch(f"/api/users/{user_id}/plex-play", json={"enabled": False})
    assert disable.status_code == 200
    assert disable.json()["plex_play_enabled"] is False

    reenable = await client.patch(f"/api/users/{user_id}/plex-play", json={"enabled": True})
    assert reenable.json()["plex_play_enabled"] is True


async def test_plex_play_change_is_audit_logged(client):
    _, user_id = await _standard_client(client, "plexplayaudit")
    await client.patch(f"/api/users/{user_id}/plex-play", json={"enabled": False})

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    matching = [e for e in entries if e["action"] == "user.plex_play_changed"]
    assert len(matching) == 1
    assert "deaktiveret" in matching[0]["detail"]


async def test_updating_unknown_user_returns_404(client):
    response = await client.patch(
        "/api/users/000000000000000000000000/plex-play", json={"enabled": False}
    )
    assert response.status_code == 404


async def test_availability_omits_play_url_when_disabled_for_this_user(client, monkeypatch):
    """CLAUDE.md regel 16 — reel håndhævelse i backend, ikke kun en skjult
    knap i UI'et: `play_url` skal være fysisk fraværende fra svaret, ikke
    kun ignoreret af frontend."""
    from app.integrations.plex_client import PlexItem

    _configure(monkeypatch)
    standard, user_id = await _standard_client(client, "plexplaydisabled")
    await client.patch(f"/api/users/{user_id}/plex-play", json={"enabled": False})

    created = await standard.post(
        "/api/movies", json={"title": "The Matrix", "year": 1999, "media_type": "Digital", "format": "D-1080"}
    )
    movie_id = created.json()["id"]
    _patch_library(monkeypatch, [PlexItem("movie", "42", "The Matrix", 1999, None, None)])

    response = await standard.get("/api/plex/availability?kind=movie")
    body = response.json()
    assert body["play_allowed"] is False
    # Badge/tilstedeværelse er stadig med — kun selve linket er fjernet.
    assert body["items"][movie_id]["available"] is True
    assert body["items"][movie_id]["play_url"] is None


async def test_availability_keeps_play_url_when_enabled(client, monkeypatch):
    from app.integrations.plex_client import PlexItem

    _configure(monkeypatch)
    created = await client.post(
        "/api/movies", json={"title": "The Matrix", "year": 1999, "media_type": "Digital", "format": "D-1080"}
    )
    movie_id = created.json()["id"]
    _patch_library(monkeypatch, [PlexItem("movie", "42", "The Matrix", 1999, None, None)])

    response = await client.get("/api/plex/availability?kind=movie")
    body = response.json()
    assert body["play_allowed"] is True
    assert body["items"][movie_id]["play_url"] is not None
