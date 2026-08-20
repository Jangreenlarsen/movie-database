from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.repositories import system_settings_repository


async def test_get_requires_login_but_not_admin(client):
    """Feature #177/#186 — bevidst ikke admin-only: enhver bruger skal selv
    kunne læse den aktuelle politik, for at UI'et kan afspejle den korrekt."""
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
            json={"require_preferred_at": False},
        )
        assert response.status_code == 403


async def test_default_policy_matches_feature_176s_shipped_behaviour(client):
    response = await client.get("/api/settings/screening-request-policy")
    assert response.status_code == 200
    assert response.json() == {"require_preferred_at": True}


async def test_updating_the_policy_takes_effect_immediately(client):
    response = await client.patch(
        "/api/settings/screening-request-policy",
        json={"require_preferred_at": False},
    )
    assert response.status_code == 200
    assert response.json()["require_preferred_at"] is False
    assert settings.require_preferred_at is False


async def test_policy_change_is_audit_logged_with_the_actual_value(client):
    """Ikke en hemmelighed (bare en boolean) — audit-loggen må gerne vise
    den faktiske nye værdi, samme princip som password_policy.updated."""
    await client.patch(
        "/api/settings/screening-request-policy",
        json={"require_preferred_at": False},
    )

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    matching = [e for e in entries if e["action"] == "screening_request_policy.updated"]
    assert len(matching) == 1
    assert "require_preferred_at=False" in matching[0]["detail"]


# Feature #186 — omdøbningen af require_preferred_at_for_guests til
# require_preferred_at må ikke stille miste en admins tidligere satte
# override under det gamle feltnavn.


async def test_migration_carries_over_an_existing_override_under_the_old_field_name(db):
    await db[system_settings_repository.COLLECTION].update_one(
        {"_id": system_settings_repository.DOC_ID},
        {"$set": {"require_preferred_at_for_guests": False}},
        upsert=True,
    )

    await system_settings_repository.migrate_screening_request_policy_field_rename(db)

    doc = await db[system_settings_repository.COLLECTION].find_one(
        {"_id": system_settings_repository.DOC_ID}
    )
    assert doc["require_preferred_at"] is False
    assert "require_preferred_at_for_guests" not in doc


async def test_migration_is_a_no_op_when_the_old_field_is_absent(db):
    await system_settings_repository.migrate_screening_request_policy_field_rename(db)
    doc = await db[system_settings_repository.COLLECTION].find_one(
        {"_id": system_settings_repository.DOC_ID}
    )
    assert doc is None or "require_preferred_at_for_guests" not in doc
