async def test_wishlist_movie_has_no_serial_number(client):
    response = await client.post(
        "/api/movies", json={"title": "Wishlist Movie", "is_wishlist": True}
    )
    assert response.status_code == 201
    movie = response.json()
    assert movie["is_wishlist"] is True
    assert movie["serial_number"] is None


async def test_library_and_wishlist_listings_are_separate(client):
    await client.post("/api/movies", json={"title": "Owned Movie"})
    await client.post("/api/movies", json={"title": "Wanted Movie", "is_wishlist": True})

    library = await client.get("/api/movies")
    assert [m["title"] for m in library.json()] == ["Owned Movie"]

    wishlist = await client.get("/api/movies", params={"wishlist": "true"})
    assert [m["title"] for m in wishlist.json()] == ["Wanted Movie"]


async def test_multiple_wishlist_movies_can_be_created(client):
    """Regression coverage mirroring BUGS.md #1/#10 — omitting `serial_number`
    entirely (rather than storing it as null) must not trip the sparse
    unique index when several wishlist items are created."""
    first = await client.post("/api/movies", json={"title": "Wish One", "is_wishlist": True})
    second = await client.post("/api/movies", json={"title": "Wish Two", "is_wishlist": True})
    assert first.status_code == 201
    assert second.status_code == 201
