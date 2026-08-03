from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_reset_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second:
        register = await second.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        await client.patch(
            f"/api/users/{register.json()['id']}/status", json={"status": "active"}
        )
        response = await second.post(
            "/api/system/reset", json={"current_password": "testpassword123"}
        )
        assert response.status_code == 403


async def test_reset_rejects_wrong_password(client):
    await client.post("/api/movies", json={"title": "Should Survive"})

    response = await client.post(
        "/api/system/reset", json={"current_password": "wrong-password"}
    )
    assert response.status_code == 401

    movies = await client.get("/api/movies")
    assert len(movies.json()["items"]) == 1


async def test_reset_clears_library_and_related_data(client):
    await client.post("/api/movies", json={"title": "Doomed Movie", "tags": ["x"]})
    await client.post("/api/tv-shows", json={"name": "Doomed Show"})
    created = await client.post("/api/movies", json={"title": "Deleted Doomed Movie"})
    await client.delete(f"/api/movies/{created.json()['id']}")
    movie_for_screening = await client.post("/api/movies", json={"title": "Screening Movie"})
    movie_id = movie_for_screening.json()["id"]
    await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2026-09-01T20:00:00"},
    )

    response = await client.post(
        "/api/system/reset", json={"current_password": "testpassword123"}
    )
    assert response.status_code == 200
    result = response.json()
    # 2 still-active movies ("Doomed Movie", "Screening Movie") — the third
    # was soft-deleted and lives in deleted_movies instead.
    assert result["movies_removed"] == 2
    assert result["tv_shows_removed"] == 1
    assert result["deleted_movies_removed"] == 1
    assert result["tags_removed"] == 1
    assert result["screenings_removed"] == 1
    assert result["screening_requests_removed"] == 1

    assert (await client.get("/api/movies")).json()["items"] == []
    assert (await client.get("/api/tv-shows")).json()["items"] == []
    assert (await client.get("/api/movies/deleted")).json() == []
    assert (await client.get("/api/tags")).json() == []
    assert (await client.get("/api/screenings")).json() == []
    assert (await client.get("/api/screening-requests")).json() == []


async def test_reset_does_not_touch_users_or_system_settings(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "discogs_token", "keep-me")

    await client.post("/api/system/reset", json={"current_password": "testpassword123"})

    me = await client.get("/api/users/me")
    assert me.status_code == 200
    assert me.json()["username"] == "testuser"

    system_settings = await client.get("/api/settings/system")
    assert system_settings.json()["discogs_token"]["source"] == "env"


async def test_serial_numbers_restart_after_reset(client):
    first = await client.post("/api/movies", json={"title": "Before Reset"})
    assert first.json()["serial_number"] == 1

    await client.post("/api/system/reset", json={"current_password": "testpassword123"})

    after = await client.post("/api/movies", json={"title": "After Reset"})
    assert after.json()["serial_number"] == 1


async def test_reset_is_audit_logged(client):
    await client.post("/api/movies", json={"title": "One Movie"})
    await client.post("/api/system/reset", json={"current_password": "testpassword123"})

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["action"] == "database.reset"
    assert entries[0]["actor"] == "testuser"
