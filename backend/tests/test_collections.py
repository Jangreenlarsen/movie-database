from app.integrations import tmdb_client


def _fake_details(tmdb_id, title, collection_id=None, collection_name=None):
    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "year": 2001,
        "poster_url": None,
        "overview": None,
        "genres": [],
        "cast": [],
        "director": None,
        "rating": None,
        "runtime": None,
        "imdb_url": None,
        "trailer_url": None,
        "collection_id": collection_id,
        "collection_name": collection_name,
    }


def _fake_collection(collection_id, parts):
    return {
        "id": collection_id,
        "name": "Some Trilogy",
        "poster_url": "http://img/collection.jpg",
        "parts": parts,
    }


async def test_movie_without_collection_has_null_fields(client):
    response = await client.post("/api/movies", json={"title": "Standalone", "media_type": "Fysisk", "format": "F-DVD"})
    assert response.json()["collection_id"] is None
    assert response.json()["collection_name"] is None


async def test_movie_stores_collection_from_tmdb(client, monkeypatch):
    async def fake_get_movie_details(tmdb_id):
        return _fake_details(tmdb_id, "Part One", collection_id=99, collection_name="Some Trilogy")

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)
    response = await client.post("/api/movies", json={"tmdb_id": 1, "media_type": "Fysisk", "format": "F-DVD"})
    assert response.json()["collection_id"] == 99
    assert response.json()["collection_name"] == "Some Trilogy"


async def test_collection_endpoint_marks_owned_and_missing_parts(client, monkeypatch):
    async def fake_get_movie_details(tmdb_id):
        return _fake_details(tmdb_id, f"Part {tmdb_id}", collection_id=99, collection_name="Some Trilogy")

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)
    created = await client.post("/api/movies", json={"tmdb_id": 1, "media_type": "Fysisk", "format": "F-DVD"})
    owned_movie_id = created.json()["id"]

    async def fake_get_collection(collection_id):
        return _fake_collection(
            collection_id,
            [
                {"tmdb_id": 1, "title": "Part 1", "year": 2000, "poster_url": None},
                {"tmdb_id": 2, "title": "Part 2", "year": 2001, "poster_url": None},
                {"tmdb_id": 3, "title": "Part 3", "year": 2002, "poster_url": None},
            ],
        )

    monkeypatch.setattr(tmdb_client, "get_collection", fake_get_collection)

    response = await client.get("/api/movies/collections/99")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Some Trilogy"
    assert len(data["parts"]) == 3

    part_1 = next(p for p in data["parts"] if p["tmdb_id"] == 1)
    part_2 = next(p for p in data["parts"] if p["tmdb_id"] == 2)
    assert part_1["owned"] is True
    assert part_1["owned_movie_id"] == owned_movie_id
    assert part_1["owned_is_wishlist"] is False
    assert part_2["owned"] is False
    assert part_2["owned_movie_id"] is None


async def test_collection_endpoint_marks_wishlist_parts(client, monkeypatch):
    async def fake_get_movie_details(tmdb_id):
        return _fake_details(tmdb_id, "Wishlisted Part", collection_id=5, collection_name="A Saga")

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)
    await client.post("/api/movies", json={"tmdb_id": 7, "is_wishlist": True})

    async def fake_get_collection(collection_id):
        return _fake_collection(
            collection_id, [{"tmdb_id": 7, "title": "Wishlisted Part", "year": 2010, "poster_url": None}]
        )

    monkeypatch.setattr(tmdb_client, "get_collection", fake_get_collection)

    response = await client.get("/api/movies/collections/5")
    part = response.json()["parts"][0]
    assert part["owned"] is True
    assert part["owned_is_wishlist"] is True


async def test_sync_refreshes_collection_fields(client, monkeypatch):
    async def fake_initial(tmdb_id):
        return _fake_details(tmdb_id, "Movie", collection_id=None, collection_name=None)

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_initial)
    created = await client.post("/api/movies", json={"tmdb_id": 1, "media_type": "Fysisk", "format": "F-DVD"})
    assert created.json()["collection_id"] is None

    async def fake_refreshed(tmdb_id):
        return _fake_details(tmdb_id, "Movie", collection_id=42, collection_name="Newly Discovered Series")

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_refreshed)
    await client.post("/api/movies/sync-tmdb")

    refreshed = await client.get(f"/api/movies/{created.json()['id']}")
    assert refreshed.json()["collection_id"] == 42
    assert refreshed.json()["collection_name"] == "Newly Discovered Series"
