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
    assert [m["title"] for m in library.json()["items"]] == ["Owned Movie"]

    wishlist = await client.get("/api/movies", params={"wishlist": "true"})
    assert [m["title"] for m in wishlist.json()["items"]] == ["Wanted Movie"]


async def test_multiple_wishlist_movies_can_be_created(client):
    """Regression coverage mirroring BUGS.md #1/#10 — omitting `serial_number`
    entirely (rather than storing it as null) must not trip the sparse
    unique index when several wishlist items are created."""
    first = await client.post("/api/movies", json={"title": "Wish One", "is_wishlist": True})
    second = await client.post("/api/movies", json={"title": "Wish Two", "is_wishlist": True})
    assert first.status_code == 201
    assert second.status_code == 201


async def test_moving_a_wishlist_movie_to_the_library_assigns_a_serial_number(client):
    """Regression test for FEATURES.md #32 — once you actually own a
    wishlisted movie, moving it to the library must assign it a real
    serial_number, same as a freshly-created library movie would get."""
    create = await client.post(
        "/api/movies", json={"title": "Finally Got It", "is_wishlist": True}
    )
    movie_id = create.json()["id"]
    assert create.json()["serial_number"] is None

    response = await client.patch(f"/api/movies/{movie_id}", json={"is_wishlist": False})
    assert response.status_code == 200
    moved = response.json()
    assert moved["is_wishlist"] is False
    assert moved["serial_number"] is not None
    assert moved["serial_number"] > 0

    # It must now show up in the library listing, not the wishlist.
    library = await client.get("/api/movies")
    assert "Finally Got It" in [m["title"] for m in library.json()["items"]]
    wishlist = await client.get("/api/movies", params={"wishlist": "true"})
    assert "Finally Got It" not in [m["title"] for m in wishlist.json()["items"]]


async def test_moving_a_wishlist_movie_to_the_library_is_not_gated_by_registrant(client):
    """Assigning a first serial number when leaving the wishlist behaves like
    creation (anyone can do it), not like renumbering an existing movie."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        register = await standard_client.post(
            "/api/auth/register", json={"username": "wishuser", "password": "testpassword123"}
        )
        await client.patch(
            f"/api/users/{register.json()['id']}/status", json={"status": "active"}
        )
        create = await standard_client.post(
            "/api/movies", json={"title": "Someone Else's Wish", "is_wishlist": True}
        )
        movie_id = create.json()["id"]

    # `client` fixture's user ("testuser") did not register this movie.
    response = await client.patch(f"/api/movies/{movie_id}", json={"is_wishlist": False})
    assert response.status_code == 200
    assert response.json()["serial_number"] is not None


async def test_moving_a_library_movie_to_the_wishlist_clears_its_serial_number(client):
    create = await client.post("/api/movies", json={"title": "Regretted Purchase"})
    movie_id = create.json()["id"]
    assert create.json()["serial_number"] is not None

    response = await client.patch(f"/api/movies/{movie_id}", json={"is_wishlist": True})
    assert response.status_code == 200
    assert response.json()["is_wishlist"] is True
    assert response.json()["serial_number"] is None
