import httpx
import pytest

from app.core.errors import TmdbUnavailableError
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
