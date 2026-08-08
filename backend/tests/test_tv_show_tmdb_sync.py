from httpx import ASGITransport, AsyncClient

from app.integrations import tmdb_client
from app.main import app


def _fake_tv_details(tmdb_id, name="Refreshed Show", seasons=None, rating=9.5):
    if seasons is None:
        seasons = [
            {
                "season_number": 1,
                "name": "Season 1",
                "episode_count": 7,
                "air_date": "2008-01-20",
                "poster_url": None,
            },
            {
                "season_number": 2,
                "name": "Season 2",
                "episode_count": 13,
                "air_date": "2009-03-08",
                "poster_url": None,
            },
        ]
    return {
        "tmdb_id": tmdb_id,
        "name": name,
        "year": 2008,
        "end_year": 2013,
        "status": "Ended",
        "poster_url": "http://img/new.jpg",
        "overview": "Updated overview.",
        "genres": ["Drama"],
        "cast": ["New Cast Member"],
        "creators": ["New Creator"],
        "rating": rating,
        "number_of_seasons": len(seasons),
        "number_of_episodes": sum(s["episode_count"] for s in seasons),
        "imdb_id": "tt_new",
        "imdb_url": "https://www.imdb.com/title/tt_new/",
        "seasons": seasons,
    }


def _fake_episodes(season_number, count):
    return [
        {"episode_number": n, "name": f"Episode {n}", "air_date": "2008-01-20"}
        for n in range(1, count + 1)
    ]


async def test_sync_refreshes_tmdb_fields_without_touching_user_data(client, monkeypatch):
    async def fake_initial_details(tv_id):
        return _fake_tv_details(tv_id, name="Original Name", rating=5.0)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_initial_details)

    create = await client.post(
        "/api/tv-shows",
        json={"tmdb_id": 1396, "tags": ["Favorite"], "format": "DVD", "location": "Stuen", "media_type": "Fysisk"},
    )
    show_id = create.json()["id"]
    serial_number = create.json()["serial_number"]

    async def fake_refreshed_details(tv_id):
        return _fake_tv_details(tv_id, name="Refreshed Name", rating=9.5)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_refreshed_details)

    response = await client.post("/api/tv-shows/sync-tmdb")
    assert response.status_code == 200
    assert response.json() == {
        "total": 1,
        "synced": 1,
        "failed": 0,
        "failed_titles": [],
        "stopped_early": False,
    }

    updated = await client.get(f"/api/tv-shows/{show_id}")
    show = updated.json()
    assert show["name"] == "Refreshed Name"
    assert show["rating"] == 9.5
    # User-entered fields must survive untouched.
    assert show["tags"] == ["Favorite", "Tilføjet af testuser"]
    assert show["format"] == "DVD"
    assert show["location"] == "Stuen"
    assert show["serial_number"] == serial_number


async def test_sync_preserves_season_ownership_and_episode_watched_status(client, monkeypatch):
    """The TV-specific counterpart to "user data" for a movie: which seasons
    are owned and which episodes are watched must survive a metadata
    refresh, even though the season's own TMDb metadata (episode_count
    etc.) is refreshed (FEATURES.md #57)."""

    async def fake_initial_details(tv_id):
        return _fake_tv_details(tv_id)

    async def fake_season_details(tv_id, season_number):
        return _fake_episodes(season_number, 7)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_initial_details)
    monkeypatch.setattr(tmdb_client, "get_season_details", fake_season_details)

    create = await client.post("/api/tv-shows", json={"tmdb_id": 1396, "media_type": "Fysisk", "format": "DVD"})
    show_id = create.json()["id"]
    await client.patch(f"/api/tv-shows/{show_id}/seasons/1", json={"owned": True})
    await client.patch(f"/api/tv-shows/{show_id}/seasons/1/episodes/3", json={"watched": True})

    # TMDb now reports a corrected episode_count for season 1.
    async def fake_refreshed_details(tv_id):
        return _fake_tv_details(
            tv_id,
            seasons=[
                {
                    "season_number": 1,
                    "name": "Season 1",
                    "episode_count": 8,
                    "air_date": "2008-01-20",
                    "poster_url": None,
                },
                {
                    "season_number": 2,
                    "name": "Season 2",
                    "episode_count": 13,
                    "air_date": "2009-03-08",
                    "poster_url": None,
                },
            ],
        )

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_refreshed_details)

    response = await client.post("/api/tv-shows/sync-tmdb")
    assert response.status_code == 200
    assert response.json()["synced"] == 1

    updated = await client.get(f"/api/tv-shows/{show_id}")
    season_1 = next(s for s in updated.json()["seasons"] if s["season_number"] == 1)
    assert season_1["owned"] is True
    assert season_1["episode_count"] == 8  # refreshed from TMDb
    assert len(season_1["episodes"]) == 7  # cached episodes preserved
    ep3 = next(e for e in season_1["episodes"] if e["episode_number"] == 3)
    assert ep3["watched"] is True  # watched-status preserved


async def test_sync_adds_newly_announced_season_as_unowned(client, monkeypatch):
    async def fake_initial_details(tv_id):
        return _fake_tv_details(tv_id)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_initial_details)
    create = await client.post("/api/tv-shows", json={"tmdb_id": 1396, "media_type": "Fysisk", "format": "DVD"})
    show_id = create.json()["id"]

    async def fake_renewed_details(tv_id):
        details = _fake_tv_details(
            tv_id,
            seasons=[
                {"season_number": 1, "name": "Season 1", "episode_count": 7,
                 "air_date": "2008-01-20", "poster_url": None},
                {"season_number": 2, "name": "Season 2", "episode_count": 13,
                 "air_date": "2009-03-08", "poster_url": None},
                {"season_number": 3, "name": "Season 3", "episode_count": 10,
                 "air_date": "2026-01-01", "poster_url": None},
            ],
        )
        return details

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_renewed_details)

    response = await client.post("/api/tv-shows/sync-tmdb")
    assert response.status_code == 200

    updated = await client.get(f"/api/tv-shows/{show_id}")
    seasons = updated.json()["seasons"]
    assert len(seasons) == 3
    season_3 = next(s for s in seasons if s["season_number"] == 3)
    assert season_3["owned"] is False
    assert season_3["episodes"] == []


async def test_sync_skips_manually_created_tv_shows(client, monkeypatch):
    await client.post("/api/tv-shows", json={"name": "No TMDb Link", "media_type": "Fysisk", "format": "DVD"})

    called = {"n": 0}

    async def fake_get_tv_show_details(tv_id):
        called["n"] += 1
        return _fake_tv_details(tv_id)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)

    response = await client.post("/api/tv-shows/sync-tmdb")
    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "synced": 0,
        "failed": 0,
        "failed_titles": [],
        "stopped_early": False,
    }
    assert called["n"] == 0


async def test_sync_continues_past_a_single_show_failure(client, monkeypatch):
    from app.core.errors import TmdbNotFoundError

    async def fake_initial_details(tv_id):
        return _fake_tv_details(tv_id, name=f"Show {tv_id}")

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_initial_details)
    await client.post("/api/tv-shows", json={"tmdb_id": 1, "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/tv-shows", json={"tmdb_id": 2, "media_type": "Fysisk", "format": "DVD"})

    async def flaky_details(tv_id):
        if tv_id == 1:
            raise TmdbNotFoundError(tv_id)
        return _fake_tv_details(tv_id, name="Show 2 Refreshed")

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", flaky_details)

    response = await client.post("/api/tv-shows/sync-tmdb")
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 2
    assert result["synced"] == 1
    assert result["failed"] == 1
    assert result["failed_titles"] == ["Show 1"]


async def test_sync_stops_early_on_rate_limit_instead_of_failing_every_show(client, monkeypatch):
    from app.core.errors import TmdbRateLimitedError

    async def fake_initial_details(tv_id):
        return _fake_tv_details(tv_id, name=f"Show {tv_id}")

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_initial_details)
    await client.post("/api/tv-shows", json={"tmdb_id": 1, "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/tv-shows", json={"tmdb_id": 2, "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/tv-shows", json={"tmdb_id": 3, "media_type": "Fysisk", "format": "DVD"})

    call_count = {"n": 0}

    async def rate_limited_after_first(tv_id):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_tv_details(tv_id, name="Show 1 Refreshed")
        raise TmdbRateLimitedError()

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", rate_limited_after_first)

    response = await client.post("/api/tv-shows/sync-tmdb")
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 3
    assert result["synced"] == 1
    assert result["failed"] == 2
    assert result["stopped_early"] is True
    assert call_count["n"] == 2


async def test_sync_short_circuits_when_token_missing(client, monkeypatch):
    from app.core.config import settings

    async def fake_initial_details(tv_id):
        return _fake_tv_details(tv_id)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_initial_details)
    await client.post("/api/tv-shows", json={"tmdb_id": 99, "media_type": "Fysisk", "format": "DVD"})

    called = {"n": 0}

    async def fake_get_tv_show_details(tv_id):
        called["n"] += 1
        return _fake_tv_details(tv_id)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)
    monkeypatch.setattr(settings, "tmdb_api_token", "")

    response = await client.post("/api/tv-shows/sync-tmdb")
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    assert result["stopped_early"] is True
    assert called["n"] == 0


async def test_sync_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        response = await standard_client.post("/api/tv-shows/sync-tmdb")
        assert response.status_code == 403
