"""Feature #146 — sortering på genre."""


async def _movie(client, title, genres):
    await client.post(
        "/api/movies",
        json={"title": title, "media_type": "Fysisk", "format": "F-DVD", "genres": genres},
    )


async def test_sort_movies_by_genre_ascending(client):
    # Én genre pr. film → deterministisk på tværs af mongomock og ægte MongoDB
    # (array-sort på ét element = det element).
    await _movie(client, "A", ["Horror"])
    await _movie(client, "B", ["Action"])
    await _movie(client, "C", ["Comedy"])

    resp = await client.get("/api/movies", params={"sort": "genres:asc"})
    assert resp.status_code == 200
    titles = [m["title"] for m in resp.json()["items"]]
    assert titles == ["B", "C", "A"]  # Action, Comedy, Horror


async def test_sort_movies_by_genre_descending(client):
    await _movie(client, "A", ["Horror"])
    await _movie(client, "B", ["Action"])
    await _movie(client, "C", ["Comedy"])

    resp = await client.get("/api/movies", params={"sort": "genres:desc"})
    titles = [m["title"] for m in resp.json()["items"]]
    assert titles == ["A", "C", "B"]  # Horror, Comedy, Action
