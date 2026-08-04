from httpx import ASGITransport, AsyncClient

from app.core.config import ENV_DEFAULT_API_KEYS, settings
from app.integrations import tmdb_client
from app.main import app


async def test_system_settings_require_admin(client, monkeypatch):
    monkeypatch.setattr(settings, "tmdb_api_token", "")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        get_response = await standard_client.get("/api/settings/system")
        patch_response = await standard_client.patch(
            "/api/settings/system", json={"tmdb_api_token": "sneaky"}
        )
        assert get_response.status_code == 403
        assert patch_response.status_code == 403


async def test_unset_key_reports_unset(client, monkeypatch):
    monkeypatch.setattr(settings, "tmdb_api_token", "")

    response = await client.get("/api/settings/system")
    assert response.status_code == 200
    assert response.json()["tmdb_api_token"] == {"configured": False, "source": "unset"}


async def test_env_sourced_key_reports_env(client, monkeypatch):
    monkeypatch.setattr(settings, "discogs_token", "env-value-abc")

    response = await client.get("/api/settings/system")
    assert response.json()["discogs_token"] == {"configured": True, "source": "env"}


async def test_setting_a_key_activates_it_immediately_without_leaking_value(client, monkeypatch):
    monkeypatch.setattr(settings, "tmdb_api_token", "")

    response = await client.patch("/api/settings/system", json={"tmdb_api_token": "brand-new-secret"})

    assert response.status_code == 200
    assert response.json()["tmdb_api_token"] == {"configured": True, "source": "custom"}
    # The raw secret must never appear anywhere in the response body.
    assert "brand-new-secret" not in response.text
    # The live settings singleton is mutated immediately — no restart needed.
    assert settings.tmdb_api_token == "brand-new-secret"


async def test_clearing_a_custom_key_reverts_to_env_default(client, monkeypatch):
    monkeypatch.setattr(settings, "discogs_token", "original-env-key")
    monkeypatch.setitem(ENV_DEFAULT_API_KEYS, "discogs_token", "original-env-key")

    first = await client.patch("/api/settings/system", json={"discogs_token": "override-key"})
    assert first.json()["discogs_token"]["source"] == "custom"
    assert settings.discogs_token == "override-key"

    second = await client.patch("/api/settings/system", json={"discogs_token": ""})
    assert second.json()["discogs_token"] == {"configured": True, "source": "env"}
    assert settings.discogs_token == "original-env-key"


async def test_omitted_fields_are_left_untouched(client, monkeypatch):
    monkeypatch.setattr(settings, "tmdb_api_token", "existing-tmdb")
    monkeypatch.setattr(settings, "omdb_api_key", "existing-omdb")

    response = await client.patch("/api/settings/system", json={"discogs_token": "new-discogs"})

    assert response.status_code == 200
    assert settings.tmdb_api_token == "existing-tmdb"
    assert settings.omdb_api_key == "existing-omdb"
    assert settings.discogs_token == "new-discogs"


async def test_override_persists_across_requests(client, monkeypatch):
    monkeypatch.setattr(settings, "tmdb_api_token", "")

    await client.patch("/api/settings/system", json={"tmdb_api_token": "persisted-value"})
    response = await client.get("/api/settings/system")

    assert response.json()["tmdb_api_token"] == {"configured": True, "source": "custom"}


async def test_omdb_api_key_behaves_like_the_other_secrets(client, monkeypatch):
    monkeypatch.setattr(settings, "omdb_api_key", "")

    response = await client.patch("/api/settings/system", json={"omdb_api_key": "omdb-secret-abc"})
    assert response.json()["omdb_api_key"] == {"configured": True, "source": "custom"}
    assert "omdb-secret-abc" not in response.text
    assert settings.omdb_api_key == "omdb-secret-abc"


async def test_upcdatabase_token_behaves_like_the_other_secrets(client, monkeypatch):
    monkeypatch.setattr(settings, "upcdatabase_token", "")

    response = await client.patch(
        "/api/settings/system", json={"upcdatabase_token": "upcdatabase-secret-abc"}
    )
    assert response.json()["upcdatabase_token"] == {"configured": True, "source": "custom"}
    assert "upcdatabase-secret-abc" not in response.text
    assert settings.upcdatabase_token == "upcdatabase-secret-abc"


async def test_plex_token_behaves_like_the_other_secrets(client, monkeypatch):
    monkeypatch.setattr(settings, "plex_token", "")

    response = await client.patch("/api/settings/system", json={"plex_token": "plex-secret-abc"})
    assert response.json()["plex_token"] == {"configured": True, "source": "custom"}
    assert "plex-secret-abc" not in response.text
    assert settings.plex_token == "plex-secret-abc"


async def test_clearing_override_survives_a_key_missing_from_env_defaults(client, monkeypatch):
    """Regression test for BUGS.md #30: if a new overridable key is ever
    added to OVERRIDABLE_KEYS/SystemSettingsUpdate without also adding it to
    ENV_DEFAULT_API_KEYS in config.py, clearing its override used to raise
    a bare KeyError (-> 500) instead of degrading gracefully."""
    monkeypatch.setattr(settings, "discogs_token", "original-env-key")
    monkeypatch.setitem(ENV_DEFAULT_API_KEYS, "discogs_token", "original-env-key")

    first = await client.patch("/api/settings/system", json={"discogs_token": "override-key"})
    assert first.json()["discogs_token"]["source"] == "custom"

    monkeypatch.delitem(ENV_DEFAULT_API_KEYS, "discogs_token")

    second = await client.patch("/api/settings/system", json={"discogs_token": ""})
    assert second.status_code == 200
    assert settings.discogs_token == ""


async def test_plex_server_url_is_returned_with_its_actual_value(client, monkeypatch):
    """Unlike every other field on this endpoint, plex_server_url is not a
    secret — it should round-trip as plain text, not a masked status."""
    monkeypatch.setattr(settings, "plex_server_url", "")

    response = await client.patch(
        "/api/settings/system", json={"plex_server_url": "http://192.168.1.50:32400"}
    )
    assert response.status_code == 200
    assert response.json()["plex_server_url"] == "http://192.168.1.50:32400"

    get_response = await client.get("/api/settings/system")
    assert get_response.json()["plex_server_url"] == "http://192.168.1.50:32400"


# Feature #75 — "Test forbindelse".


async def test_test_connection_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin3", "password": "testpassword123"}
        )
        response = await standard_client.post("/api/settings/system/test/tmdb_api_token")
        assert response.status_code == 403


async def test_test_connection_rejects_unknown_key(client):
    response = await client.post("/api/settings/system/test/plex_token")
    assert response.status_code == 422


async def test_test_connection_dispatches_to_the_right_client(client, monkeypatch):
    async def fake_test_connection():
        return True, "Virker"

    monkeypatch.setattr(tmdb_client, "test_connection", fake_test_connection)

    response = await client.post("/api/settings/system/test/tmdb_api_token")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "Virker"}


async def test_test_connection_reports_failure_message(client, monkeypatch):
    async def fake_test_connection():
        return False, "TMDb afviste nøglen (ugyldig)"

    monkeypatch.setattr(tmdb_client, "test_connection", fake_test_connection)

    response = await client.post("/api/settings/system/test/tmdb_api_token")
    assert response.status_code == 200
    assert response.json() == {"ok": False, "message": "TMDb afviste nøglen (ugyldig)"}
