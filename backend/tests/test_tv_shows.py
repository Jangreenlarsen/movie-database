from app.integrations import tmdb_client


def _fake_tv_details(
    tmdb_id,
    name="Breaking Bad",
    seasons=None,
    imdb_id="tt0903747",
):
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
        "poster_url": "http://img/bb.jpg",
        "overview": "A chemistry teacher turns to crime.",
        "genres": ["Drama", "Crime"],
        "cast": ["Bryan Cranston"],
        "creators": ["Vince Gilligan"],
        "rating": 8.9,
        "number_of_seasons": len(seasons),
        "number_of_episodes": sum(s["episode_count"] for s in seasons),
        "imdb_id": imdb_id,
        "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
        "seasons": seasons,
    }


def _fake_episodes(season_number, count):
    return [
        {"episode_number": n, "name": f"Episode {n}", "air_date": "2008-01-20"}
        for n in range(1, count + 1)
    ]


async def test_create_tv_show_manually(client):
    response = await client.post("/api/tv-shows", json={"name": "My Show", "media_type": "Fysisk", "format": "F-DVD"})
    assert response.status_code == 201
    show = response.json()
    assert show["name"] == "My Show"
    assert show["serial_number"] == 1
    assert show["seasons"] == []


async def test_create_tv_show_requires_tmdb_id_or_name(client):
    response = await client.post("/api/tv-shows", json={})
    assert response.status_code == 422


async def test_create_tv_show_from_tmdb_fetches_metadata_and_light_seasons(client, monkeypatch):
    async def fake_get_tv_show_details(tv_id):
        assert tv_id == 1396
        return _fake_tv_details(1396)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)

    response = await client.post("/api/tv-shows", json={"tmdb_id": 1396, "tags": ["Favorite"], "media_type": "Fysisk", "format": "F-DVD"})
    assert response.status_code == 201
    show = response.json()
    assert show["name"] == "Breaking Bad"
    assert show["creators"] == ["Vince Gilligan"]
    assert show["number_of_seasons"] == 2
    assert show["rating"] == 8.9
    assert len(show["seasons"]) == 2
    # Light season list only — no episodes fetched yet (lazy-load).
    assert show["seasons"][0]["episode_count"] == 7
    assert show["seasons"][0]["episodes"] == []
    assert show["seasons"][0]["owned"] is False
    assert show["tags"] == ["Favorite", "Tilføjet af testuser"]


async def test_create_tv_show_marks_owned_seasons_and_fetches_their_episodes(client, monkeypatch):
    """Feature #54 bundled into creation itself (BUGS.md #28): the caller no
    longer has to POST-then-PATCH-per-season, which used to leave a
    duplicate-prone half-finished show behind if a PATCH failed."""

    async def fake_get_tv_show_details(tv_id):
        return _fake_tv_details(tv_id)

    async def fake_get_season_details(tv_id, season_number):
        assert season_number == 2
        return _fake_episodes(season_number, 13)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)
    monkeypatch.setattr(tmdb_client, "get_season_details", fake_get_season_details)

    response = await client.post(
        "/api/tv-shows", json={"tmdb_id": 1396, "owned_seasons": [2], "media_type": "Fysisk", "format": "F-DVD"}
    )
    assert response.status_code == 201
    seasons = response.json()["seasons"]

    season_1 = next(s for s in seasons if s["season_number"] == 1)
    assert season_1["owned"] is False
    assert season_1["episodes"] == []

    season_2 = next(s for s in seasons if s["season_number"] == 2)
    assert season_2["owned"] is True
    assert len(season_2["episodes"]) == 13


async def test_create_tv_show_owned_season_survives_tmdb_episode_fetch_failure(client, monkeypatch):
    """A TMDb failure while fetching one season's episodes must not fail
    the whole creation — the season still ends up owned, just without a
    cached episode list yet (self-heals on the next owned-toggle)."""
    from app.core.errors import TmdbUnavailableError

    async def fake_get_tv_show_details(tv_id):
        return _fake_tv_details(tv_id)

    async def failing_get_season_details(tv_id, season_number):
        raise TmdbUnavailableError("TMDb er nede")

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)
    monkeypatch.setattr(tmdb_client, "get_season_details", failing_get_season_details)

    response = await client.post(
        "/api/tv-shows", json={"tmdb_id": 1396, "owned_seasons": [1], "media_type": "Fysisk", "format": "F-DVD"}
    )
    assert response.status_code == 201
    season_1 = next(s for s in response.json()["seasons"] if s["season_number"] == 1)
    assert season_1["owned"] is True
    assert season_1["episodes"] == []


async def test_tv_show_serial_numbers_are_independent_from_movies(client):
    await client.post("/api/movies", json={"title": "A Movie", "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/movies", json={"title": "Another Movie", "media_type": "Fysisk", "format": "F-DVD"})

    show = await client.post("/api/tv-shows", json={"name": "A Show", "media_type": "Fysisk", "format": "F-DVD"})
    assert show.json()["serial_number"] == 1


async def test_wishlist_tv_show_has_no_serial_number(client):
    response = await client.post(
        "/api/tv-shows", json={"name": "Wanted Show", "is_wishlist": True}
    )
    assert response.json()["serial_number"] is None
    assert response.json()["is_wishlist"] is True


async def test_get_missing_tv_show_returns_404(client):
    response = await client.get("/api/tv-shows/000000000000000000000000")
    assert response.status_code == 404


async def test_filter_tv_shows_by_genre_matches_any_selected(client):
    """Feature #111 — se den identiske test i test_movies.py."""
    await client.post(
        "/api/tv-shows",
        json={"name": "Horror Show", "genres": ["Horror"], "media_type": "Fysisk", "format": "F-DVD"},
    )
    await client.post(
        "/api/tv-shows",
        json={
            "name": "Action Comedy Show",
            "genres": ["Action", "Comedy"],
            "media_type": "Fysisk",
            "format": "F-DVD",
        },
    )

    by_horror = await client.get("/api/tv-shows", params={"genres": "Horror"})
    assert [s["name"] for s in by_horror.json()["items"]] == ["Horror Show"]

    by_either = await client.get("/api/tv-shows", params={"genres": "Horror,Comedy"})
    assert sorted(s["name"] for s in by_either.json()["items"]) == [
        "Action Comedy Show",
        "Horror Show",
    ]


# --- negerbare filter-badges (feature #156) ---------------------------------


async def test_filter_excludes_tv_shows_by_tag_and_genre(client):
    """Feature #156 — se den identiske test i test_movies.py."""
    await client.post(
        "/api/tv-shows",
        json={"name": "Julehygge", "tags": ["Christmas"], "genres": ["Horror"], "media_type": "Fysisk", "format": "F-DVD"},
    )
    await client.post(
        "/api/tv-shows",
        json={"name": "Uden jul", "genres": ["Comedy"], "media_type": "Fysisk", "format": "F-DVD"},
    )

    by_tag = await client.get("/api/tv-shows", params={"tags_exclude": "christmas"})
    assert [s["name"] for s in by_tag.json()["items"]] == ["Uden jul"]

    by_genre = await client.get("/api/tv-shows", params={"genres_exclude": "Horror"})
    assert [s["name"] for s in by_genre.json()["items"]] == ["Uden jul"]


async def test_list_tv_genres_returns_distinct_values_from_library(client):
    """Feature #111 — se den identiske test i test_movies.py."""
    await client.post(
        "/api/tv-shows",
        json={"name": "Horror 1", "genres": ["Horror"], "media_type": "Fysisk", "format": "F-DVD"},
    )
    await client.post(
        "/api/tv-shows",
        json={
            "name": "Horror Comedy",
            "genres": ["Horror", "Comedy"],
            "media_type": "Fysisk",
            "format": "F-DVD",
        },
    )

    response = await client.get("/api/tv-shows/genres")
    assert response.status_code == 200
    assert response.json() == ["Comedy", "Horror"]


async def test_update_tv_show_tags_and_location(client):
    created = await client.post("/api/tv-shows", json={"name": "Editable Show", "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]

    response = await client.patch(
        f"/api/tv-shows/{show_id}", json={"tags": ["Cozy"], "location": "Stuen"}
    )
    assert response.status_code == 200
    assert response.json()["tags"] == ["Cozy"]
    assert response.json()["location"] == "Stuen"


async def test_create_and_update_tv_show_subtitles_list(client):
    """Feature #123 — se den identiske test i test_movies.py."""
    create_response = await client.post(
        "/api/tv-shows",
        json={
            "name": "Undertekst-serie",
            "media_type": "Fysisk",
            "format": "F-DVD",
            "subtitles": ["DK", "Eng"],
        },
    )
    assert create_response.status_code == 201
    show = create_response.json()
    assert show["subtitles"] == ["DK", "Eng"]

    update_response = await client.patch(
        f"/api/tv-shows/{show['id']}", json={"subtitles": ["Fastbrændt DA"]}
    )
    assert update_response.status_code == 200
    assert update_response.json()["subtitles"] == ["Fastbrændt DA"]


async def test_tv_show_subtitles_string_is_migrated_to_list(client, db):
    """Feature #123 — gammel fri undertekst-streng konverteres til liste."""
    from app.repositories import tv_show_repository

    await db[tv_show_repository.COLLECTION].insert_one(
        {"name": "Gammel serie", "media_type": "Fysisk", "format": "F-DVD", "subtitles": "Dansk og Engelsk"}
    )
    await tv_show_repository.ensure_indexes(db)
    doc = await db[tv_show_repository.COLLECTION].find_one({"name": "Gammel serie"})
    assert doc["subtitles"] == ["DK", "Eng"]


async def test_delete_tv_show_logs_and_allows_manual_serial_reuse(client):
    created = await client.post("/api/tv-shows", json={"name": "Doomed Show", "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]
    assert created.json()["serial_number"] == 1

    delete_response = await client.delete(f"/api/tv-shows/{show_id}")
    assert delete_response.status_code == 204

    deleted_list = await client.get("/api/tv-shows/deleted")
    assert len(deleted_list.json()) == 1
    assert deleted_list.json()[0]["name"] == "Doomed Show"

    # The auto-incrementing counter itself doesn't rewind on delete...
    recreated = await client.post("/api/tv-shows", json={"name": "New Show", "media_type": "Fysisk", "format": "F-DVD"})
    assert recreated.json()["serial_number"] == 2

    # ...but #1 is no longer taken, so it can be manually reassigned.
    reassigned = await client.patch(
        f"/api/tv-shows/{recreated.json()['id']}", json={"serial_number": 1}
    )
    assert reassigned.json()["serial_number"] == 1


async def test_move_wishlist_tv_show_to_library_assigns_serial(client):
    created = await client.post(
        "/api/tv-shows", json={"name": "Wishlisted Show", "is_wishlist": True}
    )
    show_id = created.json()["id"]

    # Feature #92 — se den identiske note i test_wishlist.py.
    response = await client.patch(
        f"/api/tv-shows/{show_id}", json={"is_wishlist": False, "media_type": "Fysisk"}
    )
    assert response.status_code == 200
    assert response.json()["serial_number"] == 1


async def test_check_duplicate_finds_existing_show(client, monkeypatch):
    async def fake_get_tv_show_details(tv_id):
        return _fake_tv_details(tv_id, name="Some Show")

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)
    created = await client.post("/api/tv-shows", json={"tmdb_id": 42, "media_type": "Fysisk", "format": "F-DVD"})

    response = await client.get("/api/tv-shows/check-duplicate", params={"tmdb_id": 42})
    matches = response.json()
    assert len(matches) == 1
    assert matches[0]["name"] == "Some Show"
    assert matches[0]["serial_number"] == created.json()["serial_number"]


async def test_search_filter_and_sort(client):
    await client.post("/api/tv-shows", json={"name": "Alpha Show", "format": "F-BD", "media_type": "Fysisk"})
    await client.post("/api/tv-shows", json={"name": "Beta Show", "format": "F-DVD", "media_type": "Fysisk"})

    filtered = await client.get("/api/tv-shows", params={"format": "F-BD"})
    assert [s["name"] for s in filtered.json()["items"]] == ["Alpha Show"]

    sorted_asc = await client.get("/api/tv-shows", params={"sort": "name:asc"})
    assert [s["name"] for s in sorted_asc.json()["items"]] == ["Alpha Show", "Beta Show"]


async def test_personal_rating_and_note(client):
    created = await client.post("/api/tv-shows", json={"name": "Rateable Show", "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]

    response = await client.patch(
        f"/api/tv-shows/{show_id}", json={"personal_rating": 9, "personal_note": "So good"}
    )
    assert response.json()["personal_rating"] == 9
    assert response.json()["personal_note"] == "So good"


async def test_top_level_watched_toggle(client):
    created = await client.post("/api/tv-shows", json={"name": "Finished Show", "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]

    response = await client.patch(
        f"/api/tv-shows/{show_id}", json={"watched": True, "watched_at": "2026-08-01"}
    )
    assert response.json()["watched"] is True

    filtered = await client.get("/api/tv-shows", params={"watched": "true"})
    assert len(filtered.json()["items"]) == 1


async def test_marking_season_owned_lazily_fetches_episodes(client, monkeypatch):
    async def fake_get_tv_show_details(tv_id):
        return _fake_tv_details(tv_id)

    async def fake_get_season_details(tv_id, season_number):
        assert season_number == 1
        return _fake_episodes(1, 7)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)
    monkeypatch.setattr(tmdb_client, "get_season_details", fake_get_season_details)

    created = await client.post("/api/tv-shows", json={"tmdb_id": 1396, "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]
    assert created.json()["seasons"][0]["episodes"] == []

    response = await client.patch(
        f"/api/tv-shows/{show_id}/seasons/1", json={"owned": True}
    )
    assert response.status_code == 200
    season_1 = next(s for s in response.json()["seasons"] if s["season_number"] == 1)
    assert season_1["owned"] is True
    assert len(season_1["episodes"]) == 7
    assert season_1["episodes"][0]["name"] == "Episode 1"
    assert season_1["episodes"][0]["watched"] is False

    # Season 2 untouched.
    season_2 = next(s for s in response.json()["seasons"] if s["season_number"] == 2)
    assert season_2["owned"] is False
    assert season_2["episodes"] == []


async def test_marking_season_unowned_does_not_clear_cached_episodes(client, monkeypatch):
    async def fake_get_tv_show_details(tv_id):
        return _fake_tv_details(tv_id)

    async def fake_get_season_details(tv_id, season_number):
        return _fake_episodes(season_number, 7)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)
    monkeypatch.setattr(tmdb_client, "get_season_details", fake_get_season_details)

    created = await client.post("/api/tv-shows", json={"tmdb_id": 1396, "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]
    await client.patch(f"/api/tv-shows/{show_id}/seasons/1", json={"owned": True})

    response = await client.patch(f"/api/tv-shows/{show_id}/seasons/1", json={"owned": False})
    season_1 = next(s for s in response.json()["seasons"] if s["season_number"] == 1)
    assert season_1["owned"] is False
    assert len(season_1["episodes"]) == 7  # still cached


async def test_marking_season_owned_twice_does_not_refetch(client, monkeypatch):
    call_count = {"n": 0}

    async def fake_get_tv_show_details(tv_id):
        return _fake_tv_details(tv_id)

    async def fake_get_season_details(tv_id, season_number):
        call_count["n"] += 1
        return _fake_episodes(season_number, 7)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)
    monkeypatch.setattr(tmdb_client, "get_season_details", fake_get_season_details)

    created = await client.post("/api/tv-shows", json={"tmdb_id": 1396, "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]

    await client.patch(f"/api/tv-shows/{show_id}/seasons/1", json={"owned": True})
    await client.patch(f"/api/tv-shows/{show_id}/seasons/1", json={"owned": False})
    await client.patch(f"/api/tv-shows/{show_id}/seasons/1", json={"owned": True})

    assert call_count["n"] == 1


async def test_set_episode_watched(client, monkeypatch):
    async def fake_get_tv_show_details(tv_id):
        return _fake_tv_details(tv_id)

    async def fake_get_season_details(tv_id, season_number):
        return _fake_episodes(season_number, 7)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)
    monkeypatch.setattr(tmdb_client, "get_season_details", fake_get_season_details)

    created = await client.post("/api/tv-shows", json={"tmdb_id": 1396, "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]
    await client.patch(f"/api/tv-shows/{show_id}/seasons/1", json={"owned": True})

    response = await client.patch(
        f"/api/tv-shows/{show_id}/seasons/1/episodes/3",
        json={"watched": True, "watched_at": "2026-08-02"},
    )
    assert response.status_code == 200
    season_1 = next(s for s in response.json()["seasons"] if s["season_number"] == 1)
    ep3 = next(e for e in season_1["episodes"] if e["episode_number"] == 3)
    assert ep3["watched"] is True
    assert ep3["watched_at"].startswith("2026-08-02")

    # Other episodes in the same season are untouched.
    ep1 = next(e for e in season_1["episodes"] if e["episode_number"] == 1)
    assert ep1["watched"] is False


async def test_set_episode_watched_on_unknown_season_returns_404(client):
    created = await client.post("/api/tv-shows", json={"name": "No Seasons Show", "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]

    response = await client.patch(
        f"/api/tv-shows/{show_id}/seasons/1/episodes/1", json={"watched": True}
    )
    assert response.status_code == 404


async def test_concurrent_episode_toggles_do_not_lose_writes(db, monkeypatch):
    """Regression test for BUGS.md #25: set_episode_watched used to read the
    whole season's episode list, mutate one entry, and write the whole list
    back — two concurrent toggles of *different* episodes could lose one of
    them. Reproduced empirically pre-fix as `{1: False, 2: True}`."""
    import asyncio

    from app.integrations import tmdb_client
    from app.models.tv_show import TvShowCreate
    from app.repositories import tv_show_repository
    from app.services import tv_show_service

    async def fake_get_tv_show_details(tv_id):
        return _fake_tv_details(tv_id)

    async def fake_get_season_details(tv_id, season_number):
        return _fake_episodes(season_number, 2)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)
    monkeypatch.setattr(tmdb_client, "get_season_details", fake_get_season_details)

    show = await tv_show_service.create_tv_show(db, TvShowCreate(tmdb_id=1396, media_type="Fysisk", format="F-DVD"), "tester")
    await tv_show_service.set_season_owned(db, show.id, 1, True)

    # Force the same interleaving a real (non-instant) MongoDB round-trip
    # allows, which mongomock's synchronous resolution otherwise hides.
    real_write = tv_show_repository.set_episode_watched

    async def slow_write(*args, **kwargs):
        await asyncio.sleep(0.01)
        return await real_write(*args, **kwargs)

    monkeypatch.setattr(tv_show_repository, "set_episode_watched", slow_write)

    await asyncio.gather(
        tv_show_service.set_episode_watched(db, show.id, 1, 1, True, None),
        tv_show_service.set_episode_watched(db, show.id, 1, 2, True, None),
    )

    final = await tv_show_service.get_tv_show(db, show.id)
    watched = {e.episode_number: e.watched for e in final.seasons[0].episodes}
    assert watched == {1: True, 2: True}


async def test_tmdb_search_endpoint(client, monkeypatch):
    async def fake_search_tv(query):
        assert query == "Breaking"
        return [{"tmdb_id": 1396, "title": "Breaking Bad", "year": 2008, "poster_url": None}]

    monkeypatch.setattr(tmdb_client, "search_tv", fake_search_tv)

    response = await client.get("/api/tv-shows/tmdb-search", params={"query": "Breaking"})
    assert response.status_code == 200
    assert response.json()[0]["title"] == "Breaking Bad"
    assert response.json()[0]["media_kind"] == "tv"


async def test_tmdb_preview_endpoint_returns_seasons_without_saving(client, monkeypatch):
    async def fake_get_tv_show_details(tv_id):
        assert tv_id == 1396
        return _fake_tv_details(1396)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)

    response = await client.get("/api/tv-shows/tmdb-preview/1396")
    assert response.status_code == 200
    seasons = response.json()
    assert [s["season_number"] for s in seasons] == [1, 2]
    assert all(s["owned"] is False for s in seasons)
    assert all(s["episodes"] == [] for s in seasons)

    # Nothing was persisted — the show list is still empty.
    list_response = await client.get("/api/tv-shows")
    assert list_response.json()["items"] == []


async def test_tmdb_preview_returns_429_on_tmdb_rate_limit(client, monkeypatch):
    """Regression test for BUGS.md #24: TmdbRateLimitedError used to have no
    exception handler and propagated as a raw 500."""
    from app.core.errors import TmdbRateLimitedError

    async def fake_get_tv_show_details(tv_id):
        raise TmdbRateLimitedError()

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)

    response = await client.get("/api/tv-shows/tmdb-preview/1396")
    assert response.status_code == 429


async def test_attribute_options_reuses_movie_enums(client):
    response = await client.get("/api/tv-shows/attribute-options")
    assert response.status_code == 200
    data = response.json()
    assert "F-BD" in data["formats"]
    assert data["subtitles"] == ["Eng", "DK"]  # feature #123


async def test_tv_shows_require_authentication(raw_client):
    response = await raw_client.get("/api/tv-shows")
    assert response.status_code == 401
