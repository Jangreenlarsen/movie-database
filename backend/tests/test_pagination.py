async def test_movies_list_is_unpaginated_by_default(client):
    """Regression guard for feature #15 — omitting page/page_size must still
    return every match (Print-siden/Voldby BIO's søgning rely on this),
    not silently truncate to a default page size."""
    for i in range(5):
        await client.post("/api/movies", json={"title": f"Movie {i}", "media_type": "Fysisk", "format": "DVD"})

    response = await client.get("/api/movies")
    data = response.json()
    assert len(data["items"]) == 5
    assert data["total"] == 5


async def test_movies_pagination_returns_correct_page_and_total(client):
    await client.post("/api/movies", json={"title": "Apple", "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/movies", json={"title": "Banana", "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/movies", json={"title": "Cherry", "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/movies", json={"title": "Date", "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/movies", json={"title": "Elderberry", "media_type": "Fysisk", "format": "DVD"})

    first_page = await client.get(
        "/api/movies", params={"sort": "title:asc", "page": 1, "page_size": 2}
    )
    data = first_page.json()
    assert [m["title"] for m in data["items"]] == ["Apple", "Banana"]
    assert data["total"] == 5

    second_page = await client.get(
        "/api/movies", params={"sort": "title:asc", "page": 2, "page_size": 2}
    )
    data = second_page.json()
    assert [m["title"] for m in data["items"]] == ["Cherry", "Date"]
    assert data["total"] == 5

    third_page = await client.get(
        "/api/movies", params={"sort": "title:asc", "page": 3, "page_size": 2}
    )
    data = third_page.json()
    assert [m["title"] for m in data["items"]] == ["Elderberry"]
    assert data["total"] == 5


async def test_movies_pagination_beyond_last_page_returns_empty_items(client):
    await client.post("/api/movies", json={"title": "Only Movie", "media_type": "Fysisk", "format": "DVD"})

    response = await client.get("/api/movies", params={"page": 5, "page_size": 10})
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 1


async def test_movies_pagination_respects_filters_in_total_count(client):
    await client.post("/api/movies", json={"title": "Tagged", "tags": ["Christmas"], "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/movies", json={"title": "Untagged", "media_type": "Fysisk", "format": "DVD"})

    response = await client.get(
        "/api/movies", params={"tags": "christmas", "page": 1, "page_size": 10}
    )
    data = response.json()
    assert data["total"] == 1
    assert [m["title"] for m in data["items"]] == ["Tagged"]


async def test_tv_shows_pagination_returns_correct_page_and_total(client):
    await client.post("/api/tv-shows", json={"name": "Alpha", "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/tv-shows", json={"name": "Beta", "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/tv-shows", json={"name": "Gamma", "media_type": "Fysisk", "format": "DVD"})

    first_page = await client.get(
        "/api/tv-shows", params={"sort": "name:asc", "page": 1, "page_size": 2}
    )
    data = first_page.json()
    assert [s["name"] for s in data["items"]] == ["Alpha", "Beta"]
    assert data["total"] == 3

    second_page = await client.get(
        "/api/tv-shows", params={"sort": "name:asc", "page": 2, "page_size": 2}
    )
    data = second_page.json()
    assert [s["name"] for s in data["items"]] == ["Gamma"]
    assert data["total"] == 3


async def test_tv_shows_list_is_unpaginated_by_default(client):
    for i in range(3):
        await client.post("/api/tv-shows", json={"name": f"Show {i}", "media_type": "Fysisk", "format": "DVD"})

    response = await client.get("/api/tv-shows")
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 3


async def test_page_without_page_size_is_ignored(client):
    """Both `page` and `page_size` must be present to actually paginate —
    a lone `page` with no `page_size` falls back to the unbounded default
    rather than dividing by an undefined page size."""
    await client.post("/api/movies", json={"title": "Solo", "media_type": "Fysisk", "format": "DVD"})

    response = await client.get("/api/movies", params={"page": 1})
    data = response.json()
    assert len(data["items"]) == 1
    assert data["total"] == 1
