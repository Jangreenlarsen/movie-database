from httpx import ASGITransport, AsyncClient

from app.core.config import ENV_DEFAULT_API_KEYS, settings
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
    monkeypatch.setattr(settings, "upc_api_key", "original-env-key")
    monkeypatch.setitem(ENV_DEFAULT_API_KEYS, "upc_api_key", "original-env-key")

    first = await client.patch("/api/settings/system", json={"upc_api_key": "override-key"})
    assert first.json()["upc_api_key"]["source"] == "custom"
    assert settings.upc_api_key == "override-key"

    second = await client.patch("/api/settings/system", json={"upc_api_key": ""})
    assert second.json()["upc_api_key"] == {"configured": True, "source": "env"}
    assert settings.upc_api_key == "original-env-key"


async def test_omitted_fields_are_left_untouched(client, monkeypatch):
    monkeypatch.setattr(settings, "tmdb_api_token", "existing-tmdb")
    monkeypatch.setattr(settings, "upc_api_key", "existing-upc")

    response = await client.patch("/api/settings/system", json={"discogs_token": "new-discogs"})

    assert response.status_code == 200
    assert settings.tmdb_api_token == "existing-tmdb"
    assert settings.upc_api_key == "existing-upc"
    assert settings.discogs_token == "new-discogs"


async def test_override_persists_across_requests(client, monkeypatch):
    monkeypatch.setattr(settings, "tmdb_api_token", "")

    await client.patch("/api/settings/system", json={"tmdb_api_token": "persisted-value"})
    response = await client.get("/api/settings/system")

    assert response.json()["tmdb_api_token"] == {"configured": True, "source": "custom"}
