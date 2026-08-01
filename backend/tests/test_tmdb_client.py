import httpx
import pytest

from app.core.errors import TmdbRateLimitedError, TmdbUnavailableError
from app.integrations import tmdb_client


def test_rating_preserves_zero():
    """Regression test for BUGS.md #8 — a genuine 0.0 vote_average must not
    be treated the same as 'no rating data'."""
    assert tmdb_client._rating(0.0) == 0.0
    assert tmdb_client._rating(None) is None
    assert tmdb_client._rating(7.891) == 7.9


def test_raise_for_status_wraps_unexpected_statuses():
    """Regression test for BUGS.md #9 — any TMDb status we don't explicitly
    enumerate elsewhere must still become a clean TmdbUnavailableError
    instead of an unhandled httpx.HTTPStatusError."""
    response = httpx.Response(
        status_code=500,
        request=httpx.Request("GET", "https://api.themoviedb.org/3/movie/1"),
    )
    with pytest.raises(TmdbUnavailableError):
        tmdb_client._raise_for_status(response)


def test_raise_for_status_allows_2xx():
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "https://api.themoviedb.org/3/movie/1"),
    )
    tmdb_client._raise_for_status(response)  # should not raise


def test_imdb_url_builds_link_from_id():
    assert tmdb_client._imdb_url("tt0133093") == "https://www.imdb.com/title/tt0133093/"
    assert tmdb_client._imdb_url(None) is None
    assert tmdb_client._imdb_url("") is None


def test_trailer_url_picks_first_official_youtube_trailer():
    videos = [
        {"site": "YouTube", "type": "Featurette", "key": "not-a-trailer"},
        {"site": "Vimeo", "type": "Trailer", "key": "wrong-site"},
        {"site": "YouTube", "type": "Trailer", "key": "vKQi3bBA1y8"},
        {"site": "YouTube", "type": "Trailer", "key": "second-trailer"},
    ]
    assert tmdb_client._trailer_url(videos) == "https://www.youtube.com/watch?v=vKQi3bBA1y8"


def test_trailer_url_returns_none_when_no_trailer_present():
    assert tmdb_client._trailer_url([]) is None
    assert tmdb_client._trailer_url([{"site": "YouTube", "type": "Teaser", "key": "x"}]) is None


def test_trailer_url_skips_entries_missing_a_key():
    """A trailer entry without a `key` must not produce a broken
    "...watch?v=None" URL — it's skipped in favor of the next candidate."""
    videos = [
        {"site": "YouTube", "type": "Trailer", "key": None},
        {"site": "YouTube", "type": "Trailer", "key": ""},
        {"site": "YouTube", "type": "Trailer", "key": "real-key"},
    ]
    assert tmdb_client._trailer_url(videos) == "https://www.youtube.com/watch?v=real-key"


async def test_get_movie_details_raises_rate_limited_on_429(monkeypatch):
    async def fake_get(self, url, headers=None, params=None):
        return httpx.Response(
            429, request=httpx.Request("GET", url), json={"status_message": "rate limited"}
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(tmdb_client.settings, "tmdb_api_token", "dummy-token")

    with pytest.raises(TmdbRateLimitedError):
        await tmdb_client.get_movie_details(603)
