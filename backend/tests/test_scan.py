from app.core.errors import TmdbUnavailableError
from app.integrations import discogs_client, tmdb_client, upc_client, upcdatabase_client
from app.services import scan_service


async def _no_tv_matches(query):
    """Default TV-search stub for scan-lookup tests that only care about
    the movie side — feature #49 makes lookup_by_barcode search both."""
    return []


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
    monkeypatch.setattr(tmdb_client, "search_tv", _no_tv_matches)

    response = await client.post("/api/scan/lookup", json={"barcode": "012569059406"})
    assert response.status_code == 200
    data = response.json()
    assert data["guessed_title"] == "The Matrix (DVD)"
    assert data["candidates"][0]["tmdb_id"] == 603
    assert data["candidates"][0]["media_kind"] == "movie"


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
    monkeypatch.setattr(tmdb_client, "search_tv", _no_tv_matches)

    response = await client.post("/api/scan/lookup", json={"barcode": "5051890012345"})
    assert response.status_code == 200
    data = response.json()
    assert data["guessed_title"] == "The Matrix (DVD)"
    assert data["candidates"][0]["tmdb_id"] == 603


async def test_scan_lookup_falls_back_to_upcdatabase_when_discogs_has_no_match(client, monkeypatch):
    """Regression test for FEATURES.md #69 — when both UPCitemdb and Discogs
    miss, UPCDatabase.org should be tried as a third fallback."""

    async def fake_upc_lookup_title(barcode):
        return None

    async def fake_discogs_lookup_title(barcode):
        return None

    async def fake_upcdatabase_lookup_title(barcode):
        assert barcode == "5051890012345"
        return "The Matrix (DVD)"

    async def fake_search_movies(query):
        assert query == "The Matrix (DVD)"
        return [{"tmdb_id": 603, "title": "The Matrix", "year": 1999, "poster_url": None}]

    monkeypatch.setattr(upc_client, "lookup_title", fake_upc_lookup_title)
    monkeypatch.setattr(discogs_client, "lookup_title", fake_discogs_lookup_title)
    monkeypatch.setattr(upcdatabase_client, "lookup_title", fake_upcdatabase_lookup_title)
    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    monkeypatch.setattr(tmdb_client, "search_tv", _no_tv_matches)

    response = await client.post("/api/scan/lookup", json={"barcode": "5051890012345"})
    assert response.status_code == 200
    data = response.json()
    assert data["guessed_title"] == "The Matrix (DVD)"
    assert data["candidates"][0]["tmdb_id"] == 603


def test_alternate_upc_ean_form_strips_leading_zero_from_ean13():
    assert scan_service._alternate_upc_ean_form("0012569059406") == "012569059406"


def test_alternate_upc_ean_form_adds_leading_zero_to_upca():
    assert scan_service._alternate_upc_ean_form("012569059406") == "0012569059406"


def test_alternate_upc_ean_form_none_for_ean13_without_leading_zero():
    """A genuine 13-digit EAN that doesn't start with 0 isn't a UPC-A in
    disguise — no alternate form to try."""
    assert scan_service._alternate_upc_ean_form("5051890012345") is None


def test_alternate_upc_ean_form_none_for_non_digit_or_wrong_length():
    assert scan_service._alternate_upc_ean_form("not-a-barcode") is None
    assert scan_service._alternate_upc_ean_form("12345") is None


async def test_scan_lookup_retries_with_alternate_upc_ean_form(client, monkeypatch):
    """Regression test for BUGS.md #19 — a barcode scanned/reported in one
    length (e.g. EAN-13 with leading zero) must still find a match if the
    lookup service only has it indexed under the other length (UPC-A)."""

    async def fake_upc_lookup_title(barcode):
        # Only matches the 12-digit UPC-A form, not the scanned 13-digit one.
        return "The Matrix (DVD)" if barcode == "012569059406" else None

    async def fake_discogs_lookup_title(barcode):
        return None

    async def fake_search_movies(query):
        return [{"tmdb_id": 603, "title": "The Matrix", "year": 1999, "poster_url": None}]

    monkeypatch.setattr(upc_client, "lookup_title", fake_upc_lookup_title)
    monkeypatch.setattr(discogs_client, "lookup_title", fake_discogs_lookup_title)
    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    monkeypatch.setattr(tmdb_client, "search_tv", _no_tv_matches)

    response = await client.post("/api/scan/lookup", json={"barcode": "0012569059406"})
    assert response.status_code == 200
    data = response.json()
    assert data["guessed_title"] == "The Matrix (DVD)"
    assert data["candidates"][0]["tmdb_id"] == 603


async def test_scan_lookup_no_match_even_after_alternate_form(client, monkeypatch):
    async def fake_lookup_title(barcode):
        return None

    monkeypatch.setattr(upc_client, "lookup_title", fake_lookup_title)
    monkeypatch.setattr(discogs_client, "lookup_title", fake_lookup_title)

    response = await client.post("/api/scan/lookup", json={"barcode": "012569059406"})
    assert response.status_code == 200
    assert response.json() == {"guessed_title": None, "candidates": []}


async def test_scan_lookup_trims_whitespace(client, monkeypatch):
    async def fake_lookup_title(barcode):
        assert barcode == "012569059406"
        return "The Matrix (DVD)"

    async def fake_search_movies(query):
        return [{"tmdb_id": 603, "title": "The Matrix", "year": 1999, "poster_url": None}]

    monkeypatch.setattr(upc_client, "lookup_title", fake_lookup_title)
    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    monkeypatch.setattr(tmdb_client, "search_tv", _no_tv_matches)

    response = await client.post("/api/scan/lookup", json={"barcode": "  012569059406\n"})
    assert response.status_code == 200
    assert response.json()["guessed_title"] == "The Matrix (DVD)"


async def test_scan_lookup_merges_movie_and_tv_candidates(client, monkeypatch):
    """Regression test for BUGS.md #20/FEATURES.md #49 — a scanned barcode
    whose product is a TV show must actually surface as a candidate,
    tagged so the frontend can save it to the right resource."""

    async def fake_lookup_title(barcode):
        return "The Americans"

    async def fake_search_movies(query):
        return [{"tmdb_id": 24909, "title": "The Young Americans", "year": 1993, "poster_url": None}]

    async def fake_search_tv(query):
        return [{"tmdb_id": 1409, "title": "The Americans", "year": 2013, "poster_url": None}]

    monkeypatch.setattr(upc_client, "lookup_title", fake_lookup_title)
    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    monkeypatch.setattr(tmdb_client, "search_tv", fake_search_tv)

    response = await client.post("/api/scan/lookup", json={"barcode": "5039036089630"})
    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert len(candidates) == 2
    assert candidates[0]["media_kind"] == "movie"
    assert candidates[0]["title"] == "The Young Americans"
    assert candidates[1]["media_kind"] == "tv"
    assert candidates[1]["title"] == "The Americans"


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
            "director": "Lana Wachowski",
            "collection_id": None,
            "collection_name": None,
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
