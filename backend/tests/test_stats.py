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
    # Feature #159 — altid de faste 12 uger, alle med count 0, ikke en tom
    # liste: et hul i en tidsserie er misvisende.
    assert len(data["weekly_additions"]) == 12
    assert all(week["count"] == 0 for week in data["weekly_additions"])


async def test_wishlist_movies_are_excluded_from_stats(client):
    await client.post("/api/movies", json={"title": "In Library", "runtime": 100, "media_type": "Fysisk", "format": "F-DVD"})
    await client.post(
        "/api/movies", json={"title": "On Wishlist", "runtime": 200, "is_wishlist": True}
    )

    response = await client.get("/api/movies/stats")
    data = response.json()
    assert data["total_movies"] == 1
    assert data["total_runtime_minutes"] == 100


async def test_runtime_and_watched_counts(client):
    a = await client.post("/api/movies", json={"title": "A", "runtime": 90, "media_type": "Fysisk", "format": "F-DVD"})
    b = await client.post("/api/movies", json={"title": "B", "runtime": 120, "media_type": "Fysisk", "format": "F-DVD"})
    await client.patch(f"/api/movies/{a.json()['id']}", json={"watched": True})

    response = await client.get("/api/movies/stats")
    data = response.json()
    assert data["total_movies"] == 2
    assert data["total_runtime_minutes"] == 210
    assert data["watched_count"] == 1
    assert data["unwatched_count"] == 1


async def test_genre_and_format_breakdown(client):
    await client.post(
        "/api/movies", json={"title": "A", "genres": ["Action", "Drama"], "format": "F-BD", "media_type": "Fysisk"}
    )
    await client.post("/api/movies", json={"title": "B", "genres": ["Action"], "format": "F-BD", "media_type": "Fysisk"})
    await client.post("/api/movies", json={"title": "C", "genres": ["Drama"], "format": "F-DVD", "media_type": "Fysisk"})

    response = await client.get("/api/movies/stats")
    data = response.json()

    genre_counts = {g["name"]: g["count"] for g in data["genre_breakdown"]}
    assert genre_counts == {"Action": 2, "Drama": 2}

    format_counts = {f["name"]: f["count"] for f in data["format_breakdown"]}
    assert format_counts == {"F-BD": 2, "F-DVD": 1}


async def test_decade_breakdown_groups_by_decade_start(client):
    await client.post("/api/movies", json={"title": "A", "year": 1994, "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/movies", json={"title": "B", "year": 1999, "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/movies", json={"title": "C", "year": 2001, "media_type": "Fysisk", "format": "F-DVD"})

    response = await client.get("/api/movies/stats")
    data = response.json()

    decade_counts = {d["name"]: d["count"] for d in data["decade_breakdown"]}
    assert decade_counts == {"1990'erne": 2, "2000'erne": 1}


async def test_top_directors_and_actors(client):
    await client.post(
        "/api/movies",
        json={"title": "A", "director": "Denis Villeneuve", "cast": ["Timothee Chalamet"], "media_type": "Fysisk", "format": "F-DVD"},
    )
    await client.post(
        "/api/movies",
        json={"title": "B", "director": "Denis Villeneuve", "cast": ["Timothee Chalamet", "Zendaya"], "media_type": "Fysisk", "format": "F-DVD"},
    )

    response = await client.get("/api/movies/stats")
    data = response.json()

    directors = {d["name"]: d["count"] for d in data["top_directors"]}
    actors = {a["name"]: a["count"] for a in data["top_actors"]}
    assert directors == {"Denis Villeneuve": 2}
    assert actors == {"Timothee Chalamet": 2, "Zendaya": 1}


async def test_movies_without_year_or_runtime_do_not_break_stats(client):
    await client.post("/api/movies", json={"title": "No metadata at all", "media_type": "Fysisk", "format": "F-DVD"})
    response = await client.get("/api/movies/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_movies"] == 1
    assert data["total_runtime_minutes"] == 0
    assert data["decade_breakdown"] == []


# --- ugentlig tilføjelses-oversigt (feature #159) ----------------------------


async def test_weekly_additions_counts_a_freshly_created_movie_in_the_current_week(client):
    await client.post("/api/movies", json={"title": "Lige Oprettet", "media_type": "Fysisk", "format": "F-DVD"})

    response = await client.get("/api/movies/stats")
    data = response.json()

    weekly = data["weekly_additions"]
    assert len(weekly) == 12
    assert all(week["name"].startswith("Uge ") for week in weekly)
    # Den seneste (sidste) uge i den kronologiske liste er den aktuelle uge —
    # den film der lige blev oprettet skal tælle med dér.
    assert weekly[-1]["count"] == 1


async def test_weekly_additions_counts_movies_and_tv_shows_together(client):
    """Feature #159 — "ny film/tv" dækker begge ressourcer i én tælling,
    samme princip som barcode_source_breakdown allerede gør."""
    await client.post("/api/movies", json={"title": "Film", "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/tv-shows", json={"name": "Serie", "media_type": "Fysisk", "format": "F-DVD"})

    response = await client.get("/api/movies/stats")
    data = response.json()

    assert data["weekly_additions"][-1]["count"] == 2


async def test_weekly_additions_excludes_wishlist(client):
    await client.post("/api/movies", json={"title": "Ønske", "is_wishlist": True})

    response = await client.get("/api/movies/stats")
    data = response.json()

    assert data["weekly_additions"][-1]["count"] == 0
