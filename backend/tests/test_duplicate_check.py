from app.integrations import tmdb_client


def _fake_details(tmdb_id, title="Some Movie"):
    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "year": 2001,
        "poster_url": None,
        "overview": None,
        "genres": [],
        "cast": [],
        "director": None,
        "collection_id": None,
        "collection_name": None,
        "rating": None,
        "runtime": None,
        "imdb_url": None,
        "trailer_url": None,
    }


async def test_no_duplicates_for_unknown_tmdb_id(client):
    response = await client.get("/api/movies/check-duplicate", params={"tmdb_id": 999})
    assert response.status_code == 200
    assert response.json() == []


async def test_finds_existing_library_movie(client, monkeypatch):
    async def fake_get_movie_details(tmdb_id):
        return _fake_details(tmdb_id, "Already Owned")

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)
    created = await client.post("/api/movies", json={"tmdb_id": 42, "media_type": "Fysisk", "format": "DVD"})
    serial = created.json()["serial_number"]

    response = await client.get("/api/movies/check-duplicate", params={"tmdb_id": 42})
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) == 1
    assert matches[0]["title"] == "Already Owned"
    assert matches[0]["serial_number"] == serial
    assert matches[0]["is_wishlist"] is False


async def test_finds_existing_wishlist_entry(client, monkeypatch):
    async def fake_get_movie_details(tmdb_id):
        return _fake_details(tmdb_id, "Wanted Movie")

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)
    await client.post("/api/movies", json={"tmdb_id": 7, "is_wishlist": True})

    response = await client.get("/api/movies/check-duplicate", params={"tmdb_id": 7})
    matches = response.json()
    assert len(matches) == 1
    assert matches[0]["is_wishlist"] is True
    assert matches[0]["serial_number"] is None


async def test_creating_a_duplicate_is_not_blocked(client, monkeypatch):
    """Duplicate-check is a soft warning only (feature #38) — owning two
    physical copies of the same film is a legitimate use case."""

    async def fake_get_movie_details(tmdb_id):
        return _fake_details(tmdb_id, "Two Copies")

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)
    first = await client.post("/api/movies", json={"tmdb_id": 55, "media_type": "Fysisk", "format": "DVD"})
    second = await client.post("/api/movies", json={"tmdb_id": 55, "media_type": "Fysisk", "format": "DVD"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    response = await client.get("/api/movies/check-duplicate", params={"tmdb_id": 55})
    assert len(response.json()) == 2
