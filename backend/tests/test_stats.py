async def test_empty_library_has_zeroed_stats(client):
    response = await client.get("/api/movies/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_movies"] == 0
    assert data["total_runtime_minutes"] == 0
    assert data["watched_count"] == 0
    assert data["unwatched_count"] == 0
    assert data["genre_breakdown"] == []
    assert data["decade_breakdown"] == []


async def test_wishlist_movies_are_excluded_from_stats(client):
    await client.post("/api/movies", json={"title": "In Library", "runtime": 100})
    await client.post(
        "/api/movies", json={"title": "On Wishlist", "runtime": 200, "is_wishlist": True}
    )

    response = await client.get("/api/movies/stats")
    data = response.json()
    assert data["total_movies"] == 1
    assert data["total_runtime_minutes"] == 100


async def test_runtime_and_watched_counts(client):
    a = await client.post("/api/movies", json={"title": "A", "runtime": 90})
    b = await client.post("/api/movies", json={"title": "B", "runtime": 120})
    await client.patch(f"/api/movies/{a.json()['id']}", json={"watched": True})

    response = await client.get("/api/movies/stats")
    data = response.json()
    assert data["total_movies"] == 2
    assert data["total_runtime_minutes"] == 210
    assert data["watched_count"] == 1
    assert data["unwatched_count"] == 1


async def test_genre_and_format_breakdown(client):
    await client.post(
        "/api/movies", json={"title": "A", "genres": ["Action", "Drama"], "format": "BD"}
    )
    await client.post("/api/movies", json={"title": "B", "genres": ["Action"], "format": "BD"})
    await client.post("/api/movies", json={"title": "C", "genres": ["Drama"], "format": "DVD"})

    response = await client.get("/api/movies/stats")
    data = response.json()

    genre_counts = {g["name"]: g["count"] for g in data["genre_breakdown"]}
    assert genre_counts == {"Action": 2, "Drama": 2}

    format_counts = {f["name"]: f["count"] for f in data["format_breakdown"]}
    assert format_counts == {"BD": 2, "DVD": 1}


async def test_decade_breakdown_groups_by_decade_start(client):
    await client.post("/api/movies", json={"title": "A", "year": 1994})
    await client.post("/api/movies", json={"title": "B", "year": 1999})
    await client.post("/api/movies", json={"title": "C", "year": 2001})

    response = await client.get("/api/movies/stats")
    data = response.json()

    decade_counts = {d["name"]: d["count"] for d in data["decade_breakdown"]}
    assert decade_counts == {"1990'erne": 2, "2000'erne": 1}


async def test_top_directors_and_actors(client):
    await client.post(
        "/api/movies",
        json={"title": "A", "director": "Denis Villeneuve", "cast": ["Timothee Chalamet"]},
    )
    await client.post(
        "/api/movies",
        json={"title": "B", "director": "Denis Villeneuve", "cast": ["Timothee Chalamet", "Zendaya"]},
    )

    response = await client.get("/api/movies/stats")
    data = response.json()

    directors = {d["name"]: d["count"] for d in data["top_directors"]}
    actors = {a["name"]: a["count"] for a in data["top_actors"]}
    assert directors == {"Denis Villeneuve": 2}
    assert actors == {"Timothee Chalamet": 2, "Zendaya": 1}


async def test_movies_without_year_or_runtime_do_not_break_stats(client):
    await client.post("/api/movies", json={"title": "No metadata at all"})
    response = await client.get("/api/movies/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_movies"] == 1
    assert data["total_runtime_minutes"] == 0
    assert data["decade_breakdown"] == []
