from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_backup_includes_all_expected_collections(client):
    await client.post("/api/movies", json={"title": "Backup Movie", "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/tv-shows", json={"name": "Backup Show", "media_type": "Fysisk", "format": "DVD"})
    created = await client.post("/api/movies", json={"title": "Deleted Movie", "media_type": "Fysisk", "format": "DVD"})
    await client.delete(f"/api/movies/{created.json()['id']}")

    response = await client.get("/api/system/backup")
    assert response.status_code == 200
    data = response.json()

    assert len(data["movies"]) == 1
    assert len(data["tv_shows"]) == 1
    assert len(data["deleted_movies"]) == 1
    assert len(data["users"]) == 1
    assert len(data["counters"]) >= 1
    assert "backed_up_at" in data
    assert "app_version" in data
    # system_settings must never appear anywhere in the backup — the whole
    # point of excluding it (CLAUDE.md regel 6 / FEATURES.md #61).
    assert "system_settings" not in data


async def test_backup_never_exposes_api_keys(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "tmdb_api_token", "super-secret-tmdb-token")
    response = await client.get("/api/system/backup")
    assert "super-secret-tmdb-token" not in response.text


async def test_backup_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin3", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/system/backup")
        assert response.status_code == 403


async def test_restore_round_trip_preserves_everything(client):
    await client.post("/api/movies", json={"title": "Roundtrip Movie", "tags": ["Favorite"], "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/tv-shows", json={"name": "Roundtrip Show", "media_type": "Fysisk", "format": "DVD"})
    backup = (await client.get("/api/system/backup")).json()

    # Mutate everything after the backup was taken.
    await client.post("/api/movies", json={"title": "Should Disappear After Restore", "media_type": "Fysisk", "format": "DVD"})

    response = await client.post("/api/system/restore", json=backup)
    assert response.status_code == 200
    result = response.json()
    assert result["movies_imported"] == 1
    assert result["tv_shows_imported"] == 1
    assert result["users_imported"] == 1

    movies = (await client.get("/api/movies")).json()["items"]
    assert len(movies) == 1
    assert movies[0]["title"] == "Roundtrip Movie"
    assert movies[0]["tags"] == ["Favorite", "Tilføjet af testuser"]

    # The logged-in session survives the restore because the same user
    # document (same _id) came back — proves the round trip didn't corrupt
    # user documents.
    me = await client.get("/api/users/me")
    assert me.status_code == 200


async def test_restore_requires_admin(client):
    backup = (await client.get("/api/system/backup")).json()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin4", "password": "testpassword123"}
        )
        response = await standard_client.post("/api/system/restore", json=backup)
        assert response.status_code == 403
