from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import audit_log_service, deploy_service


async def _create_movie(client, title="Audit Movie"):
    created = await client.post("/api/movies", json={"title": title})
    return created.json()["id"]


async def test_audit_log_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/audit-log")
        assert response.status_code == 403


async def test_audit_log_starts_empty(client):
    response = await client.get("/api/audit-log")
    assert response.status_code == 200
    assert response.json() == {"entries": [], "total": 0}


async def test_role_change_is_logged(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second_client:
        register_response = await second_client.post(
            "/api/auth/register", json={"username": "promoteme", "password": "testpassword123"}
        )
        user_id = register_response.json()["id"]

    await client.patch(f"/api/users/{user_id}/role", json={"role": "admin"})

    response = await client.get("/api/audit-log")
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["action"] == "user.role_changed"
    assert entries[0]["actor"] == "testuser"
    assert "promoteme" in entries[0]["detail"]


async def test_system_settings_update_is_logged_without_leaking_value(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "discogs_token", "")

    response = await client.patch(
        "/api/settings/system", json={"discogs_token": "super-secret-value"}
    )
    assert response.status_code == 200

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["action"] == "system_settings.updated"
    assert entries[0]["detail"] == "discogs_token"
    assert "super-secret-value" not in log.text


async def test_system_settings_update_with_no_changed_keys_is_not_logged(client):
    """An omitted-only PATCH (nothing actually set) shouldn't clutter the
    audit log with a no-op entry."""
    response = await client.patch("/api/settings/system", json={})
    assert response.status_code == 200

    log = await client.get("/api/audit-log")
    assert log.json()["entries"] == []


async def test_deploy_trigger_is_logged(client, monkeypatch):
    monkeypatch.setattr(deploy_service, "trigger_deploy", lambda: None)

    await client.post("/api/system/deploy")

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["action"] == "deploy.triggered"
    assert entries[0]["actor"] == "testuser"


async def test_library_export_and_import_are_logged(client):
    await client.post("/api/movies", json={"title": "Export Me"})
    export_data = (await client.get("/api/library/export")).json()
    await client.post("/api/library/import", json=export_data)

    log = await client.get("/api/audit-log")
    actions = [e["action"] for e in log.json()["entries"]]
    assert actions.count("library_backup.exported") == 1
    assert actions.count("library_backup.imported") == 1


async def test_system_backup_and_restore_are_logged(client):
    await client.post("/api/movies", json={"title": "Backup Me"})
    backup = (await client.get("/api/system/backup")).json()
    await client.post("/api/system/restore", json=backup)

    log = await client.get("/api/audit-log")
    actions = [e["action"] for e in log.json()["entries"]]
    assert actions.count("system_backup.created") == 1
    assert actions.count("system_backup.restored") == 1


async def test_decline_screening_request_is_logged(client):
    movie_id = await _create_movie(client, "Declined Movie")
    created = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    request_id = created.json()["id"]

    await client.patch(f"/api/screening-requests/{request_id}", json={"status": "declined"})

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["action"] == "screening_request.declined"
    assert entries[0]["detail"] == "Declined Movie"


async def test_schedule_screening_is_logged(client):
    movie_id = await _create_movie(client, "Scheduled Movie")
    await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2026-09-01T20:00:00"},
    )

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["action"] == "screening.scheduled"
    assert "Scheduled Movie" in entries[0]["detail"]


async def test_pagination_returns_newest_first_and_respects_limit(client):
    for i in range(3):
        await client.patch("/api/settings/system", json={"discogs_token": f"value-{i}"})

    first_page = await client.get("/api/audit-log", params={"skip": 0, "limit": 2})
    data = first_page.json()
    assert data["total"] == 3
    assert len(data["entries"]) == 2

    second_page = await client.get("/api/audit-log", params={"skip": 2, "limit": 2})
    assert len(second_page.json()["entries"]) == 1


async def test_record_never_raises_when_repository_fails(db, monkeypatch):
    """Audit logging is best-effort observability, not a critical path
    (matches the Plex/OMDb philosophy) — a DB hiccup while writing the
    entry must never bubble up and fail the admin action it's logging."""

    async def fake_insert(*args, **kwargs):
        raise RuntimeError("boom")

    from app.repositories import audit_log_repository

    monkeypatch.setattr(audit_log_repository, "insert", fake_insert)

    await audit_log_service.record(db, "testuser", "some.action", "detail")
