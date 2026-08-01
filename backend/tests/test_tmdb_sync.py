from httpx import ASGITransport, AsyncClient

from app.integrations import tmdb_client
from app.main import app


def _fake_details(tmdb_id, title="Refreshed Title", rating=9.5):
    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "year": 2001,
        "poster_url": "http://img/new.jpg",
        "overview": "Updated overview.",
        "genres": ["Drama"],
        "cast": ["New Cast Member"],
        "rating": rating,
        "runtime": 111,
        "imdb_url": "https://www.imdb.com/title/tt_new/",
        "trailer_url": "https://www.youtube.com/watch?v=new",
    }


async def test_sync_refreshes_tmdb_fields_without_touching_user_data(client, monkeypatch):
    async def fake_get_movie_details(tmdb_id):
        return {
            "tmdb_id": tmdb_id,
            "title": "Original Title",
            "year": 1999,
            "poster_url": "http://img/old.jpg",
            "overview": "Old overview.",
            "genres": ["Action"],
            "cast": ["Old Cast"],
            "rating": 5.0,
            "runtime": 90,
            "imdb_url": "https://www.imdb.com/title/tt_old/",
            "trailer_url": None,
        }

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)

    create = await client.post(
        "/api/movies",
        json={"tmdb_id": 42, "tags": ["Favorite"], "format": "DVD", "location": "Stuen"},
    )
    movie_id = create.json()["id"]
    serial_number = create.json()["serial_number"]

    async def fake_refreshed_details(tmdb_id):
        return _fake_details(tmdb_id)

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_refreshed_details)

    response = await client.post("/api/movies/sync-tmdb")
    assert response.status_code == 200
    result = response.json()
    assert result == {"total": 1, "synced": 1, "failed": 0, "failed_titles": []}

    updated = await client.get(f"/api/movies/{movie_id}")
    movie = updated.json()
    assert movie["title"] == "Refreshed Title"
    assert movie["rating"] == 9.5
    assert movie["runtime"] == 111
    assert movie["imdb_url"] == "https://www.imdb.com/title/tt_new/"
    assert movie["trailer_url"] == "https://www.youtube.com/watch?v=new"
    # User-entered fields must survive untouched.
    assert movie["tags"] == ["Favorite"]
    assert movie["format"] == "DVD"
    assert movie["location"] == "Stuen"
    assert movie["serial_number"] == serial_number


async def test_sync_skips_manually_created_movies(client, monkeypatch):
    await client.post("/api/movies", json={"title": "No TMDb Link"})

    called = {"n": 0}

    async def fake_get_movie_details(tmdb_id):
        called["n"] += 1
        return _fake_details(tmdb_id)

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)

    response = await client.post("/api/movies/sync-tmdb")
    assert response.status_code == 200
    assert response.json() == {"total": 0, "synced": 0, "failed": 0, "failed_titles": []}
    assert called["n"] == 0


async def test_sync_continues_past_a_single_movie_failure(client, monkeypatch):
    from app.core.errors import TmdbNotFoundError

    async def fake_initial_details(tmdb_id):
        return _fake_details(tmdb_id, title=f"Movie {tmdb_id}")

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_initial_details)
    await client.post("/api/movies", json={"tmdb_id": 1})
    await client.post("/api/movies", json={"tmdb_id": 2})

    async def flaky_details(tmdb_id):
        if tmdb_id == 1:
            raise TmdbNotFoundError(tmdb_id)
        return _fake_details(tmdb_id, title="Movie 2 Refreshed")

    monkeypatch.setattr(tmdb_client, "get_movie_details", flaky_details)

    response = await client.post("/api/movies/sync-tmdb")
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 2
    assert result["synced"] == 1
    assert result["failed"] == 1
    assert result["failed_titles"] == ["Movie 1"]


async def test_sync_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        response = await standard_client.post("/api/movies/sync-tmdb")
        assert response.status_code == 403
