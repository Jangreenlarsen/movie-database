from app.core.config import settings
from app.integrations import omdb_client, tmdb_client
from app.services import movie_service


async def test_get_imdb_rating_returns_none_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "omdb_api_key", "")
    result = await omdb_client.get_imdb_rating("tt0133093")
    assert result is None


async def test_get_imdb_rating_returns_none_without_imdb_id(monkeypatch):
    monkeypatch.setattr(settings, "omdb_api_key", "some-key")
    result = await omdb_client.get_imdb_rating(None)
    assert result is None


async def test_resolve_rating_prefers_imdb_over_tmdb(monkeypatch):
    async def fake_get_imdb_rating(imdb_id):
        return 8.7

    monkeypatch.setattr(omdb_client, "get_imdb_rating", fake_get_imdb_rating)
    details = {"imdb_id": "tt0133093", "rating": 8.2}
    assert await movie_service._resolve_rating(details) == 8.7


async def test_resolve_rating_falls_back_to_tmdb_when_omdb_has_nothing(monkeypatch):
    async def fake_get_imdb_rating(imdb_id):
        return None

    monkeypatch.setattr(omdb_client, "get_imdb_rating", fake_get_imdb_rating)
    details = {"imdb_id": "tt0133093", "rating": 8.2}
    assert await movie_service._resolve_rating(details) == 8.2


async def test_resolve_rating_falls_back_when_no_imdb_id_at_all(monkeypatch):
    async def fake_get_imdb_rating(imdb_id):
        assert imdb_id is None
        return None

    monkeypatch.setattr(omdb_client, "get_imdb_rating", fake_get_imdb_rating)
    details = {"rating": 5.0}
    assert await movie_service._resolve_rating(details) == 5.0


def _tmdb_details(rating=8.2, imdb_id="tt0133093"):
    return {
        "tmdb_id": 603,
        "title": "The Matrix",
        "year": 1999,
        "poster_url": None,
        "overview": None,
        "genres": [],
        "cast": [],
        "director": None,
        "collection_id": None,
        "collection_name": None,
        "rating": rating,
        "runtime": None,
        "imdb_id": imdb_id,
        "imdb_url": "https://www.imdb.com/title/tt0133093/",
        "trailer_url": None,
    }


async def test_create_movie_uses_imdb_rating_when_available(client, monkeypatch):
    async def fake_get_movie_details(tmdb_id):
        return _tmdb_details(rating=8.2)

    async def fake_get_imdb_rating(imdb_id):
        assert imdb_id == "tt0133093"
        return 8.7

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)
    monkeypatch.setattr(omdb_client, "get_imdb_rating", fake_get_imdb_rating)

    response = await client.post("/api/movies", json={"tmdb_id": 603, "media_type": "Fysisk", "format": "F-DVD"})
    assert response.status_code == 201
    assert response.json()["rating"] == 8.7


async def test_create_movie_falls_back_to_tmdb_rating_without_omdb_configured(client, monkeypatch):
    """Default test environment has no OMDB_API_KEY set — confirms the
    feature is fully backward-compatible with the pre-existing behavior."""

    async def fake_get_movie_details(tmdb_id):
        return _tmdb_details(rating=8.2)

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)
    monkeypatch.setattr(settings, "omdb_api_key", "")

    response = await client.post("/api/movies", json={"tmdb_id": 603, "media_type": "Fysisk", "format": "F-DVD"})
    assert response.status_code == 201
    assert response.json()["rating"] == 8.2


async def test_sync_uses_imdb_rating_when_available(client, monkeypatch):
    async def fake_initial(tmdb_id):
        return _tmdb_details(rating=8.2)

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_initial)
    monkeypatch.setattr(settings, "omdb_api_key", "")
    created = await client.post("/api/movies", json={"tmdb_id": 603, "media_type": "Fysisk", "format": "F-DVD"})
    assert created.json()["rating"] == 8.2

    async def fake_refreshed(tmdb_id):
        return _tmdb_details(rating=8.3)

    async def fake_get_imdb_rating(imdb_id):
        return 9.0

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_refreshed)
    monkeypatch.setattr(omdb_client, "get_imdb_rating", fake_get_imdb_rating)
    await client.post("/api/movies/sync-tmdb")

    refreshed = await client.get(f"/api/movies/{created.json()['id']}")
    assert refreshed.json()["rating"] == 9.0
