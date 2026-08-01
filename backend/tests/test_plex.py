from app.integrations import plex_client
from app.services import plex_service


def test_match_prefers_tmdb_id_guid_over_title_year():
    results = [
        {
            "type": "movie",
            "title": "Different Title",
            "year": 1999,
            "ratingKey": "1",
            "Guid": [{"id": "tmdb://603"}],
        },
        {"type": "movie", "title": "The Matrix", "year": 1999, "ratingKey": "2", "Guid": []},
    ]
    assert plex_client._match_movie(results, tmdb_id=603, title="The Matrix", year=1999) == "1"


def test_match_falls_back_to_title_and_year_without_guid():
    results = [{"type": "movie", "title": "The Matrix", "year": 1999, "ratingKey": "2", "Guid": []}]
    assert plex_client._match_movie(results, tmdb_id=603, title="The Matrix", year=1999) == "2"


def test_match_ignores_non_movie_results():
    results = [{"type": "show", "title": "The Matrix", "year": 1999, "ratingKey": "9"}]
    assert plex_client._match_movie(results, tmdb_id=None, title="The Matrix", year=1999) is None


def test_match_returns_none_when_nothing_matches():
    results = [{"type": "movie", "title": "Unrelated", "year": 2010, "ratingKey": "5", "Guid": []}]
    assert plex_client._match_movie(results, tmdb_id=603, title="The Matrix", year=1999) is None


def test_build_play_url(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "plex_server_url", "http://192.168.1.50:32400")
    url = plex_client.build_play_url("42", "abc123")
    assert url == (
        "http://192.168.1.50:32400/web/index.html#!/server/abc123"
        "/details?key=%2Flibrary%2Fmetadata%2F42"
    )


async def test_check_availability_returns_unavailable_when_no_match(monkeypatch):
    async def fake_find_movie(tmdb_id, title, year):
        return None

    monkeypatch.setattr(plex_client, "find_movie", fake_find_movie)
    result = await plex_service.check_availability(603, "The Matrix", 1999)
    assert result.available is False
    assert result.play_url is None


async def test_check_availability_returns_play_url_when_matched(monkeypatch):
    async def fake_find_movie(tmdb_id, title, year):
        return {"rating_key": "42", "machine_identifier": "abc123"}

    monkeypatch.setattr(plex_client, "find_movie", fake_find_movie)
    result = await plex_service.check_availability(603, "The Matrix", 1999)
    assert result.available is True
    assert "abc123" in result.play_url
    assert "42" in result.play_url


async def test_find_movie_returns_none_when_not_configured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")
    result = await plex_client.find_movie(603, "The Matrix", 1999)
    assert result is None


async def test_plex_endpoint_returns_unavailable_for_unconfigured_server(client):
    """End-to-end through the real API route — no Plex server configured in
    tests, so the endpoint must degrade cleanly, never 500."""
    created = await client.post("/api/movies", json={"title": "No Plex Here"})
    movie_id = created.json()["id"]

    response = await client.get(f"/api/movies/{movie_id}/plex")
    assert response.status_code == 200
    assert response.json() == {"available": False, "play_url": None}
