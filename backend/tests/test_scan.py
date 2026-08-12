from app.core.errors import TmdbUnavailableError
from app.integrations import discogs_client, ean_search_client, tmdb_client, upc_client, upcdatabase_client
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


async def test_scan_lookup_reports_which_source_matched(client, monkeypatch):
    """Regression test for FEATURES.md #77 — the response should carry
    which of the four sources actually resolved the title, for the
    Statistics breakdown."""

    async def fake_no_match(barcode):
        return None

    async def fake_discogs_lookup_title(barcode):
        return "The Matrix (DVD)"

    async def fake_search_movies(query):
        return [{"tmdb_id": 603, "title": "The Matrix", "year": 1999, "poster_url": None}]

    monkeypatch.setattr(upc_client, "lookup_title", fake_no_match)
    monkeypatch.setattr(discogs_client, "lookup_title", fake_discogs_lookup_title)
    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    monkeypatch.setattr(tmdb_client, "search_tv", _no_tv_matches)

    response = await client.post("/api/scan/lookup", json={"barcode": "5051890012345"})
    assert response.status_code == 200
    assert response.json()["barcode_source"] == "discogs"


async def test_lookup_title_tries_the_configured_primary_source_first(monkeypatch):
    """Regression test for FEATURES.md #77 — setting a non-default primary
    source (here upcdatabase) should try it before UPCitemdb/Discogs, not
    just as the third fallback."""
    from app.core.config import settings

    calls = []

    async def fake_upc(barcode):
        calls.append("upcitemdb")
        return None

    async def fake_discogs(barcode):
        calls.append("discogs")
        return None

    async def fake_upcdatabase(barcode):
        calls.append("upcdatabase")
        return "The Matrix (DVD)"

    monkeypatch.setattr(settings, "primary_barcode_source", "upcdatabase")
    monkeypatch.setattr(upc_client, "lookup_title", fake_upc)
    monkeypatch.setattr(discogs_client, "lookup_title", fake_discogs)
    monkeypatch.setattr(upcdatabase_client, "lookup_title", fake_upcdatabase)

    title, source = await scan_service._lookup_title("5051890012345")
    assert title == "The Matrix (DVD)"
    assert source == "upcdatabase"
    assert calls == ["upcdatabase"]  # stopped at the first (primary) match


async def test_scan_lookup_falls_back_to_ean_search_when_upcdatabase_has_no_match(client, monkeypatch):
    """Regression test for FEATURES.md #76 — when UPCitemdb, Discogs and
    UPCDatabase.org all miss, EAN-Search.org (Jan's paid account) should be
    tried as a fourth and last fallback."""

    async def fake_no_match(barcode):
        return None

    async def fake_ean_search_lookup_title(barcode):
        assert barcode == "5051890012345"
        return "The Matrix (DVD)"

    async def fake_search_movies(query):
        assert query == "The Matrix (DVD)"
        return [{"tmdb_id": 603, "title": "The Matrix", "year": 1999, "poster_url": None}]

    monkeypatch.setattr(upc_client, "lookup_title", fake_no_match)
    monkeypatch.setattr(discogs_client, "lookup_title", fake_no_match)
    monkeypatch.setattr(upcdatabase_client, "lookup_title", fake_no_match)
    monkeypatch.setattr(ean_search_client, "lookup_title", fake_ean_search_lookup_title)
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
    assert response.json() == {"guessed_title": None, "barcode_source": None, "candidates": []}


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


async def test_scan_lookup_retries_tmdb_search_after_dropping_leading_noise_words(client, monkeypatch):
    """Regression test found 2026-08-04 in production logs: a real scanned
    barcode resolved to the noisy title "Simply HE The Americans" (a
    distributor/label prefix EAN-Search.org bakes into the product title),
    which finds zero TMDb candidates as a whole string but should be found
    once the leading noise words are progressively dropped."""

    async def fake_lookup_title(barcode):
        return "Simply HE The Americans"

    async def fake_search_movies(query):
        return []

    calls = []

    async def fake_search_tv(query):
        calls.append(query)
        if query == "The Americans":
            return [{"tmdb_id": 1409, "title": "The Americans", "year": 2013, "poster_url": None}]
        return []

    monkeypatch.setattr(upc_client, "lookup_title", fake_lookup_title)
    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    monkeypatch.setattr(tmdb_client, "search_tv", fake_search_tv)

    response = await client.post("/api/scan/lookup", json={"barcode": "5039036089630"})
    assert response.status_code == 200
    data = response.json()
    assert data["guessed_title"] == "Simply HE The Americans"
    assert len(data["candidates"]) == 1
    assert data["candidates"][0]["title"] == "The Americans"
    # Tried the full phrase first, then progressively fewer leading words —
    # never skips straight to the answer.
    assert calls == ["Simply HE The Americans", "HE The Americans", "The Americans"]


async def test_scan_lookup_gives_up_after_max_leading_words_dropped(client, monkeypatch):
    """The fallback must not keep dropping words forever — a title still
    unmatched after _MAX_LEADING_WORDS_TO_DROP words is treated as a
    genuine miss, not retried into an unrelated short query."""

    async def fake_lookup_title(barcode):
        return "One Two Three Four Nomatch"

    async def fake_no_matches(query):
        return []

    monkeypatch.setattr(upc_client, "lookup_title", fake_lookup_title)
    monkeypatch.setattr(tmdb_client, "search_movies", fake_no_matches)
    monkeypatch.setattr(tmdb_client, "search_tv", fake_no_matches)

    response = await client.post("/api/scan/lookup", json={"barcode": "5039036089630"})
    assert response.status_code == 200
    data = response.json()
    assert data["guessed_title"] == "One Two Three Four Nomatch"
    assert data["candidates"] == []


async def test_search_tmdb_with_fallback_tries_full_query_first(monkeypatch):
    calls = []

    async def fake_search_movies(query):
        calls.append(query)
        return [{"tmdb_id": 1, "title": "X", "year": 2000, "poster_url": None}]

    async def fake_no_tv(query):
        return []

    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    monkeypatch.setattr(tmdb_client, "search_tv", fake_no_tv)

    movies, tv, matched_query = await scan_service._search_tmdb_with_fallback("The Matrix")
    assert matched_query == "The Matrix"
    assert calls == ["The Matrix"]  # stopped at the first (full) query
    assert movies[0]["tmdb_id"] == 1


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
        "/api/movies", json={"tmdb_id": 603, "barcode": "012569059406", "tags": ["Favorite"], "media_type": "Fysisk", "format": "F-DVD"}
    )
    assert response.status_code == 201
    movie = response.json()
    assert movie["title"] == "The Matrix"
    assert movie["genres"] == ["Action", "Science Fiction"]
    assert movie["tags"] == ["Favorite", "Tilføjet af testuser"]
    assert movie["rating"] == 8.2
    assert movie["runtime"] == 136
    assert movie["imdb_url"] == "https://www.imdb.com/title/tt0133093/"
    assert movie["trailer_url"] == "https://www.youtube.com/watch?v=vKQi3bBA1y8"


async def test_create_movie_requires_tmdb_id_or_title(client):
    response = await client.post("/api/movies", json={"tags": ["x"], "media_type": "Fysisk", "format": "F-DVD"})
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
