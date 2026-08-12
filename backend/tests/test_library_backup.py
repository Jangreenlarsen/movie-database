from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_export_includes_all_movies_and_tv_shows(client):
    await client.post("/api/movies", json={"title": "Export Movie A", "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/movies", json={"title": "Export Movie B", "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/tv-shows", json={"name": "Export Show A", "media_type": "Fysisk", "format": "F-DVD"})

    response = await client.get("/api/library/export")
    assert response.status_code == 200
    data = response.json()
    assert len(data["movies"]) == 2
    assert len(data["tv_shows"]) == 1
    assert "exported_at" in data
    assert "app_version" in data
    titles = {m["title"] for m in data["movies"]}
    assert titles == {"Export Movie A", "Export Movie B"}


async def test_export_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/library/export")
        assert response.status_code == 403


async def test_import_replaces_movies_and_tv_shows(client):
    await client.post("/api/movies", json={"title": "Original Movie", "media_type": "Fysisk", "format": "F-DVD"})
    original_export = (await client.get("/api/library/export")).json()

    # A second, unrelated movie is created after the export was taken.
    await client.post("/api/movies", json={"title": "Created After Export", "media_type": "Fysisk", "format": "F-DVD"})
    assert len((await client.get("/api/movies")).json()["items"]) == 2

    response = await client.post("/api/library/import", json=original_export)
    assert response.status_code == 200
    assert response.json() == {"movies_imported": 1, "tv_shows_imported": 0}

    movies = (await client.get("/api/movies")).json()["items"]
    assert len(movies) == 1
    assert movies[0]["title"] == "Original Movie"


async def test_import_preserves_serial_numbers_and_bumps_counter(client):
    created = await client.post("/api/movies", json={"title": "Serial Keeper", "media_type": "Fysisk", "format": "F-DVD"})
    original_serial = created.json()["serial_number"]
    export_data = (await client.get("/api/library/export")).json()

    await client.post("/api/library/import", json=export_data)

    movies = (await client.get("/api/movies")).json()["items"]
    assert movies[0]["serial_number"] == original_serial

    # The next movie created after a restore must not collide with the
    # restored serial number.
    next_movie = await client.post("/api/movies", json={"title": "Next One", "media_type": "Fysisk", "format": "F-DVD"})
    assert next_movie.json()["serial_number"] > original_serial


async def test_import_requires_admin(client):
    export_data = (await client.get("/api/library/export")).json()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin2", "password": "testpassword123"}
        )
        response = await standard_client.post("/api/library/import", json=export_data)
        assert response.status_code == 403
