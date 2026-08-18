from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


async def test_get_requires_login_but_not_admin(client):
    """Feature #177 — bevidst ikke admin-only: en gæst skal selv kunne læse
    den aktuelle politik, for at UI'et kan afspejle den korrekt."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as unauthenticated:
        response = await unauthenticated.get("/api/settings/screening-request-policy")
        assert response.status_code == 401

    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "policyreader", "password": "testpassword123"}
        )
        await client.patch(
            f"/api/users/{(await standard_client.get('/api/users/me')).json()['id']}/status",
            json={"status": "active"},
        )
        response = await standard_client.get("/api/settings/screening-request-policy")
        assert response.status_code == 200


async def test_patch_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadminpolicy177", "password": "testpassword123"}
        )
        response = await standard_client.patch(
            "/api/settings/screening-request-policy",
            json={"require_preferred_at_for_guests": False},
        )
        assert response.status_code == 403


async def test_default_policy_matches_feature_176s_shipped_behaviour(client):
    response = await client.get("/api/settings/screening-request-policy")
    assert response.status_code == 200
    assert response.json() == {"require_preferred_at_for_guests": True}


async def test_updating_the_policy_takes_effect_immediately(client):
    response = await client.patch(
        "/api/settings/screening-request-policy",
        json={"require_preferred_at_for_guests": False},
    )
    assert response.status_code == 200
    assert response.json()["require_preferred_at_for_guests"] is False
    assert settings.require_preferred_at_for_guests is False


async def test_policy_change_is_audit_logged_with_the_actual_value(client):
    """Ikke en hemmelighed (bare en boolean) — audit-loggen må gerne vise
    den faktiske nye værdi, samme princip som password_policy.updated."""
    await client.patch(
        "/api/settings/screening-request-policy",
        json={"require_preferred_at_for_guests": False},
    )

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    matching = [e for e in entries if e["action"] == "screening_request_policy.updated"]
    assert len(matching) == 1
    assert "require_preferred_at_for_guests=False" in matching[0]["detail"]
