async def test_new_movie_is_unwatched_by_default(client):
    response = await client.post("/api/movies", json={"title": "Fresh"})
    assert response.json()["watched"] is False
    assert response.json()["watched_at"] is None


async def test_mark_as_watched_with_date(client):
    created = await client.post("/api/movies", json={"title": "Seen It"})
    movie_id = created.json()["id"]

    response = await client.patch(
        f"/api/movies/{movie_id}", json={"watched": True, "watched_at": "2026-07-15"}
    )
    assert response.status_code == 200
    assert response.json()["watched"] is True
    assert response.json()["watched_at"].startswith("2026-07-15")


async def test_unmark_watched(client):
    created = await client.post("/api/movies", json={"title": "Rewatchable"})
    movie_id = created.json()["id"]
    await client.patch(f"/api/movies/{movie_id}", json={"watched": True, "watched_at": "2026-07-01"})

    response = await client.patch(
        f"/api/movies/{movie_id}", json={"watched": False, "watched_at": None}
    )
    assert response.json()["watched"] is False
    assert response.json()["watched_at"] is None


async def test_filter_by_watched_status(client):
    a = await client.post("/api/movies", json={"title": "Watched One"})
    b = await client.post("/api/movies", json={"title": "Unwatched One"})
    await client.patch(f"/api/movies/{a.json()['id']}", json={"watched": True})

    watched_only = await client.get("/api/movies", params={"watched": "true"})
    unwatched_only = await client.get("/api/movies", params={"watched": "false"})

    watched_titles = [m["title"] for m in watched_only.json()["items"]]
    unwatched_titles = [m["title"] for m in unwatched_only.json()["items"]]
    assert watched_titles == ["Watched One"]
    assert unwatched_titles == ["Unwatched One"]


async def test_no_watched_filter_returns_everything(client):
    await client.post("/api/movies", json={"title": "A"})
    await client.post("/api/movies", json={"title": "B"})

    response = await client.get("/api/movies")
    assert len(response.json()["items"]) == 2


async def test_sort_by_watched_at(client):
    a = await client.post("/api/movies", json={"title": "Earlier"})
    b = await client.post("/api/movies", json={"title": "Later"})
    await client.patch(f"/api/movies/{a.json()['id']}", json={"watched": True, "watched_at": "2026-01-01"})
    await client.patch(f"/api/movies/{b.json()['id']}", json={"watched": True, "watched_at": "2026-06-01"})

    response = await client.get("/api/movies", params={"sort": "watched_at:desc"})
    titles = [m["title"] for m in response.json()["items"]]
    assert titles.index("Later") < titles.index("Earlier")
