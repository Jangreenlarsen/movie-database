from app.integrations import tmdb_client


def _fake_movie_details(tmdb_id, title="The Matrix"):
    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "year": 1999,
        "poster_url": "http://img/matrix.jpg",
        "overview": "A hacker discovers reality is a simulation.",
        "genres": ["Action", "Science Fiction"],
        "cast": ["Keanu Reeves"],
        "director": "Lana Wachowski",
        "collection_id": None,
        "collection_name": None,
        "rating": 8.2,
        "runtime": 136,
        "imdb_url": "https://www.imdb.com/title/tt0133093/",
        "trailer_url": "https://www.youtube.com/watch?v=vKQi3bBA1y8",
        "imdb_id": "tt0133093",
    }


def _fake_tv_details(tmdb_id, name="Breaking Bad"):
    return {
        "tmdb_id": tmdb_id,
        "name": name,
        "year": 2008,
        "end_year": 2013,
        "status": "Ended",
        "poster_url": None,
        "overview": "A chemistry teacher turns to crime.",
        "genres": ["Drama"],
        "cast": ["Bryan Cranston"],
        "creators": ["Vince Gilligan"],
        "rating": 9.5,
        "number_of_seasons": 1,
        "number_of_episodes": 7,
        "imdb_url": "https://www.imdb.com/title/tt0903747/",
        "imdb_id": "tt0903747",
        "seasons": [
            {
                "season_number": 1,
                "name": "Season 1",
                "episode_count": 7,
                "air_date": "2008-01-20",
                "poster_url": None,
            }
        ],
    }


async def _fake_get_movie_details(tmdb_id):
    return _fake_movie_details(tmdb_id)


async def _fake_get_tv_show_details(tmdb_id):
    return _fake_tv_details(tmdb_id)


# Feature #79 — rent læsende TMDb-forhåndsvisninger (ingen oprettelse).


async def test_movie_tmdb_preview_returns_full_metadata_without_creating(client, monkeypatch):
    monkeypatch.setattr(tmdb_client, "get_movie_details", _fake_get_movie_details)

    response = await client.get("/api/movies/tmdb-preview/603")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "The Matrix"
    assert data["genres"] == ["Action", "Science Fiction"]
    assert data["director"] == "Lana Wachowski"
    assert data["rating"] == 8.2

    library = await client.get("/api/movies")
    assert library.json()["total"] == 0


async def test_tv_show_tmdb_full_preview_returns_full_metadata_without_creating(client, monkeypatch):
    monkeypatch.setattr(tmdb_client, "get_tv_show_details", _fake_get_tv_show_details)

    response = await client.get("/api/tv-shows/tmdb-full-preview/1396")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Breaking Bad"
    assert data["creators"] == ["Vince Gilligan"]
    assert data["number_of_seasons"] == 1
    assert "seasons" not in data

    library = await client.get("/api/tv-shows")
    assert library.json()["total"] == 0


# Feature #77 — barcode_source persisteres kun ved rigtige scan-oprettelser.


async def test_movie_creation_persists_barcode_source_when_provided(client, monkeypatch):
    monkeypatch.setattr(tmdb_client, "get_movie_details", _fake_get_movie_details)

    response = await client.post(
        "/api/movies",
        json={"tmdb_id": 603, "barcode": "5051890012345", "barcode_source": "discogs", "media_type": "Fysisk", "format": "F-DVD"},
    )
    assert response.status_code == 201
    assert response.json()["barcode_source"] == "discogs"


async def test_movie_creation_omits_barcode_source_when_not_provided(client):
    response = await client.post("/api/movies", json={"title": "Manual entry", "media_type": "Fysisk", "format": "F-DVD"})
    assert response.status_code == 201
    assert response.json()["barcode_source"] is None


async def test_movie_creation_rejects_unknown_barcode_source(client):
    response = await client.post(
        "/api/movies", json={"title": "x", "barcode_source": "not-a-real-source", "media_type": "Fysisk", "format": "F-DVD"}
    )
    assert response.status_code == 422


async def test_tv_show_creation_persists_barcode_source_when_provided(client, monkeypatch):
    monkeypatch.setattr(tmdb_client, "get_tv_show_details", _fake_get_tv_show_details)

    response = await client.post(
        "/api/tv-shows",
        json={"tmdb_id": 1396, "barcode": "5051890012345", "barcode_source": "ean_search", "media_type": "Fysisk", "format": "F-DVD"},
    )
    assert response.status_code == 201
    assert response.json()["barcode_source"] == "ean_search"


async def test_tv_show_creation_omits_barcode_source_when_not_provided(client):
    response = await client.post("/api/tv-shows", json={"name": "Manual entry", "media_type": "Fysisk", "format": "F-DVD"})
    assert response.status_code == 201
    assert response.json()["barcode_source"] is None


# Feature #77 — Statistik-siden viser breakdown for film+TV.


async def test_stats_barcode_source_breakdown_covers_movies_and_tv(client, monkeypatch):
    monkeypatch.setattr(tmdb_client, "get_movie_details", _fake_get_movie_details)
    monkeypatch.setattr(tmdb_client, "get_tv_show_details", _fake_get_tv_show_details)

    await client.post(
        "/api/movies", json={"tmdb_id": 603, "barcode": "1", "barcode_source": "upcitemdb", "media_type": "Fysisk", "format": "F-DVD"}
    )
    await client.post(
        "/api/movies", json={"tmdb_id": 604, "barcode": "2", "barcode_source": "upcitemdb", "media_type": "Fysisk", "format": "F-DVD"}
    )
    await client.post(
        "/api/tv-shows", json={"tmdb_id": 1396, "barcode": "3", "barcode_source": "discogs", "media_type": "Fysisk", "format": "F-DVD"}
    )
    await client.post("/api/movies", json={"title": "Manual, no barcode source", "media_type": "Fysisk", "format": "F-DVD"})

    response = await client.get("/api/movies/stats")
    assert response.status_code == 200
    breakdown = {item["name"]: item["count"] for item in response.json()["barcode_source_breakdown"]}
    assert breakdown == {"UPCitemdb": 2, "Discogs": 1}


async def test_stats_barcode_source_breakdown_excludes_wishlist(client, monkeypatch):
    monkeypatch.setattr(tmdb_client, "get_movie_details", _fake_get_movie_details)

    await client.post(
        "/api/movies",
        json={
            "tmdb_id": 603,
            "barcode": "1",
            "barcode_source": "upcitemdb",
            "is_wishlist": True,
        },
    )

    response = await client.get("/api/movies/stats")
    assert response.json()["barcode_source_breakdown"] == []
