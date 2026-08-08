from app.integrations import tmdb_client


def _fake_details(tmdb_id, title, cast, director):
    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "year": 2001,
        "poster_url": None,
        "overview": None,
        "genres": [],
        "cast": cast,
        "director": director,
        "collection_id": None,
        "collection_name": None,
        "rating": None,
        "runtime": None,
        "imdb_url": None,
        "trailer_url": None,
    }


def test_director_extracted_from_first_director_credit():
    crew = [
        {"name": "Some Producer", "job": "Producer"},
        {"name": "Jane Director", "job": "Director"},
        {"name": "Other Director", "job": "Director"},
    ]
    assert tmdb_client._director(crew) == "Jane Director"


def test_director_returns_none_when_no_director_credited():
    crew = [{"name": "Some Producer", "job": "Producer"}]
    assert tmdb_client._director(crew) is None


async def test_manual_movie_can_set_director(client):
    response = await client.post(
        "/api/movies", json={"title": "Indie Film", "director": "Ed Wood", "media_type": "Fysisk", "format": "DVD"}
    )
    assert response.json()["director"] == "Ed Wood"


async def test_filter_by_director(client, monkeypatch):
    async def fake_get_movie_details(tmdb_id):
        return _fake_details(tmdb_id, f"Movie {tmdb_id}", ["Actor A"], "Christopher Nolan")

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)
    await client.post("/api/movies", json={"tmdb_id": 1, "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/movies", json={"title": "Unrelated", "media_type": "Fysisk", "format": "DVD"})

    response = await client.get("/api/movies", params={"director": "Christopher Nolan"})
    titles = [m["title"] for m in response.json()["items"]]
    assert titles == ["Movie 1"]


async def test_filter_by_cast_member(client, monkeypatch):
    async def fake_get_movie_details(tmdb_id):
        return _fake_details(tmdb_id, f"Movie {tmdb_id}", ["Tom Hanks", "Other Actor"], None)

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)
    await client.post("/api/movies", json={"tmdb_id": 1, "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/movies", json={"title": "No Tom Here", "media_type": "Fysisk", "format": "DVD"})

    response = await client.get("/api/movies", params={"cast": "Tom Hanks"})
    titles = [m["title"] for m in response.json()["items"]]
    assert titles == ["Movie 1"]


async def test_no_person_filter_returns_everything(client):
    await client.post("/api/movies", json={"title": "A", "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/movies", json={"title": "B", "media_type": "Fysisk", "format": "DVD"})
    response = await client.get("/api/movies")
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2
