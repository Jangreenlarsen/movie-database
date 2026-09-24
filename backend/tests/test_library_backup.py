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


def _import_doc(oid, title, media_type, serial, **extra):
    return {
        "_id": {"$oid": oid},
        "title": title,
        "media_type": media_type,
        "format": "F-DVD" if media_type == "Fysisk" else "D-1080",
        "serial_number": serial,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "genres": [], "cast": [], "tags": [], "audio_types": [],
        **extra,
    }


async def _import(client, movies=(), tv_shows=()):
    response = await client.post("/api/library/import", json={
        "exported_at": "2026-01-01T00:00:00+00:00", "app_version": "x",
        "movies": list(movies), "tv_shows": list(tv_shows),
    })
    assert response.status_code == 200, response.text


async def test_import_keeps_each_serial_series_on_its_own_counter(client):
    """BUGS.md #103 — en import med digitale og 5000+-numre må ikke sende
    M#-tælleren op i 5000+; hver serie fortsætter fra sit eget højeste nummer."""
    await _import(client, movies=[
        _import_doc("650000000000000000000001", "Fysisk", "Fysisk", 3),
        _import_doc("650000000000000000000002", "Digital", "Digital", 300),
        _import_doc("650000000000000000000003", "Anden pulje", "Fysisk", 5001),
    ])

    physical = await client.post("/api/movies", json={"title": "Ny fysisk", "media_type": "Fysisk", "format": "F-DVD"})
    assert physical.json()["serial_number"] == 4

    digital = await client.post("/api/movies", json={"title": "Ny digital", "media_type": "Digital", "format": "D-1080"})
    assert digital.json()["serial_number"] == 301


async def test_import_keeps_tv_physical_counter_off_other_series(client):
    tv = _import_doc("650000000000000000000011", "Serie", "Fysisk", 2)
    tv["name"] = tv.pop("title")
    tv_digital = _import_doc("650000000000000000000012", "Digital serie", "Digital", 40)
    tv_digital["name"] = tv_digital.pop("title")
    await _import(client, tv_shows=[tv, tv_digital])

    created = await client.post("/api/tv-shows", json={"name": "Ny serie", "media_type": "Fysisk", "format": "F-DVD"})
    assert created.status_code == 201, created.text
    assert created.json()["serial_number"] == 3


async def test_import_moves_other_pool_counter_past_imported_numbers(client):
    from app.db import get_database
    from app.main import app
    from app.repositories import digital_serial_repository

    await _import(client, movies=[
        _import_doc("650000000000000000000021", "Anden pulje", "Fysisk", 5007),
    ])
    db = app.dependency_overrides.get(get_database, get_database)()
    assert await digital_serial_repository.next_other_serial_number(db) == 5008
