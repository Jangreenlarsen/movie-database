from app.core.errors import TmdbUnavailableError
from app.integrations import discogs_client, tmdb_client, upc_client


async def test_scan_lookup_returns_candidates(client, monkeypatch):
    async def fake_lookup_title(barcode):
        assert barcode == "012569059406"
        return "The Matrix (DVD)"

    async def fake_search_movies(query):
        assert query == "The Matrix (DVD)"
        return [
            {"tmdb_id": 603, "title": "The Matrix", "year": 1999, "poster_url": "http://img/x.jpg"}
        ]

    monkeypatch.setattr(upc_client, "lookup_title", fake_lookup_title)
    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)

    response = await client.post("/api/scan/lookup", json={"barcode": "012569059406"})
    assert response.status_code == 200
    data = response.json()
    assert data["guessed_title"] == "The Matrix (DVD)"
    assert data["candidates"][0]["tmdb_id"] == 603


async def test_scan_lookup_no_upc_match_returns_empty_candidates(client, monkeypatch):
    async def fake_upc_lookup_title(barcode):
        return None

    async def fake_discogs_lookup_title(barcode):
        return None

    monkeypatch.setattr(upc_client, "lookup_title", fake_upc_lookup_title)
    monkeypatch.setattr(discogs_client, "lookup_title", fake_discogs_lookup_title)

    response = await client.post("/api/scan/lookup", json={"barcode": "000000000000"})
    assert response.status_code == 200
    data = response.json()
    assert data["guessed_title"] is None
    assert data["candidates"] == []


async def test_scan_lookup_falls_back_to_discogs_when_upc_has_no_match(client, monkeypatch):
    """Regression test for FEATURES.md #30 — UPCitemdb's US-centric trial
    tier often misses European EAN codes; Discogs should be tried next."""

    async def fake_upc_lookup_title(barcode):
        return None

    async def fake_discogs_lookup_title(barcode):
        assert barcode == "5051890012345"
        return "The Matrix (DVD)"

    async def fake_search_movies(query):
        assert query == "The Matrix (DVD)"
        return [{"tmdb_id": 603, "title": "The Matrix", "year": 1999, "poster_url": None}]

    monkeypatch.setattr(upc_client, "lookup_title", fake_upc_lookup_title)
    monkeypatch.setattr(discogs_client, "lookup_title", fake_discogs_lookup_title)
    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)

    response = await client.post("/api/scan/lookup", json={"barcode": "5051890012345"})
    assert response.status_code == 200
    data = response.json()
    assert data["guessed_title"] == "The Matrix (DVD)"
    assert data["candidates"][0]["tmdb_id"] == 603


async def test_create_movie_from_tmdb_id_fetches_metadata(client, monkeypatch):
    async def fake_get_movie_details(tmdb_id):
        assert tmdb_id == 603
        return {
            "tmdb_id": 603,
            "title": "The Matrix",
            "year": 1999,
            "poster_url": "http://img/matrix.jpg",
            "overview": "A hacker discovers reality is a simulation.",
            "genres": ["Action", "Science Fiction"],
            "cast": ["Keanu Reeves"],
            "rating": 8.2,
            "runtime": 136,
            "imdb_url": "https://www.imdb.com/title/tt0133093/",
            "trailer_url": "https://www.youtube.com/watch?v=vKQi3bBA1y8",
        }

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)

    response = await client.post(
        "/api/movies", json={"tmdb_id": 603, "barcode": "012569059406", "tags": ["Favorite"]}
    )
    assert response.status_code == 201
    movie = response.json()
    assert movie["title"] == "The Matrix"
    assert movie["genres"] == ["Action", "Science Fiction"]
    assert movie["tags"] == ["Favorite"]
    assert movie["rating"] == 8.2
    assert movie["runtime"] == 136
    assert movie["imdb_url"] == "https://www.imdb.com/title/tt0133093/"
    assert movie["trailer_url"] == "https://www.youtube.com/watch?v=vKQi3bBA1y8"


async def test_create_movie_requires_tmdb_id_or_title(client):
    response = await client.post("/api/movies", json={"tags": ["x"]})
    assert response.status_code == 422


async def test_tmdb_search_endpoint(client, monkeypatch):
    async def fake_search_movies(query):
        return [{"tmdb_id": 1, "title": "Foo", "year": 2020, "poster_url": None}]

    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)

    response = await client.get("/api/movies/tmdb-search", params={"query": "Foo"})
    assert response.status_code == 200
    assert response.json()[0]["title"] == "Foo"


async def test_tmdb_unavailable_maps_to_502(client, monkeypatch):
    async def fake_search_movies(query):
        raise TmdbUnavailableError("token missing")

    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)

    response = await client.get("/api/movies/tmdb-search", params={"query": "Foo"})
    assert response.status_code == 502
