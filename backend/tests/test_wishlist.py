async def test_wishlist_movie_has_no_serial_number(client):
    response = await client.post(
        "/api/movies", json={"title": "Wishlist Movie", "is_wishlist": True}
    )
    assert response.status_code == 201
    movie = response.json()
    assert movie["is_wishlist"] is True
    assert movie["serial_number"] is None


async def test_library_and_wishlist_listings_are_separate(client):
    await client.post("/api/movies", json={"title": "Owned Movie", "media_type": "Fysisk", "format": "F-DVD"})
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


async def test_moving_a_wishlist_movie_to_the_library_requires_media_type_and_format(client):
    """Feature #196 — "flyt til bibliotek" er reelt den samme overgang som at
    OPRETTE biblioteks-posten (MovieCreate.require_media_type_and_format_for_library),
    så det samme krav skal håndhæves her — ellers kunne kravet omgås ved
    først at oprette på ønskelisten og derefter flytte den uden format/
    medietype sat (CLAUDE.md regel 16)."""
    create = await client.post(
        "/api/movies", json={"title": "Half-Classified Wish", "is_wishlist": True}
    )
    movie_id = create.json()["id"]

    missing_both = await client.patch(f"/api/movies/{movie_id}", json={"is_wishlist": False})
    assert missing_both.status_code == 422
    assert "media_type" in missing_both.json()["detail"]
    assert "format" in missing_both.json()["detail"]

    missing_format = await client.patch(
        f"/api/movies/{movie_id}", json={"is_wishlist": False, "media_type": "Fysisk"}
    )
    assert missing_format.status_code == 422
    assert "format" in missing_format.json()["detail"]

    # It must still be on the wishlist — the rejected attempt made no change.
    still_wishlist = await client.get("/api/movies", params={"wishlist": "true"})
    assert "Half-Classified Wish" in [m["title"] for m in still_wishlist.json()["items"]]


async def test_moving_a_wishlist_movie_to_the_library_assigns_a_serial_number(client):
    """Regression test for FEATURES.md #32 — once you actually own a
    wishlisted movie, moving it to the library must assign it a real
    serial_number, same as a freshly-created library movie would get."""
    create = await client.post(
        "/api/movies", json={"title": "Finally Got It", "is_wishlist": True}
    )
    movie_id = create.json()["id"]
    assert create.json()["serial_number"] is None

    # Feature #92 — medietypen skal med i flytningen: kun fysiske udgaver
    # nummereres, og et ønske har ingen medietype at arve fra. Feature #196
    # — format skal med i samme kald, ellers afviser backend flytningen
    # (ClassificationRequiredError, samme krav som ved oprettelse).
    response = await client.patch(
        f"/api/movies/{movie_id}",
        json={"is_wishlist": False, "media_type": "Fysisk", "format": "F-DVD"},
    )
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
    # Feature #196 — format skal med, se den identiske note ovenfor.
    response = await client.patch(
        f"/api/movies/{movie_id}",
        json={"is_wishlist": False, "media_type": "Fysisk", "format": "F-DVD"},
    )
    assert response.status_code == 200
    assert response.json()["serial_number"] is not None


async def test_order_status_persists_on_create_and_update(client):
    """Feature #114 — bestillingsstatus gemmes ved oprettelse og kan ændres
    via PATCH; en gyldig enum-værdi accepteres, og None rydder den igen."""
    create = await client.post(
        "/api/movies",
        json={"title": "On Order", "is_wishlist": True, "order_status": "Bestilt ved iMusic"},
    )
    assert create.status_code == 201
    movie = create.json()
    assert movie["order_status"] == "Bestilt ved iMusic"

    # Skift kilde, og ryd den derefter (None = ikke bestilt).
    changed = await client.patch(
        f"/api/movies/{movie['id']}", json={"order_status": "Bestilt ved Laserdisken"}
    )
    assert changed.json()["order_status"] == "Bestilt ved Laserdisken"

    cleared = await client.patch(f"/api/movies/{movie['id']}", json={"order_status": None})
    assert cleared.json()["order_status"] is None


async def test_order_status_rejects_unknown_value(client):
    """En ukendt kilde er ikke en gyldig OrderStatus — backend afviser den
    (422) i stedet for at gemme fritekst."""
    response = await client.post(
        "/api/movies",
        json={"title": "Bad Source", "is_wishlist": True, "order_status": "Bestilt ved Netto"},
    )
    assert response.status_code == 422


async def test_order_status_is_exposed_in_attribute_options(client):
    response = await client.get("/api/movies/attribute-options")
    assert response.status_code == 200
    statuses = response.json()["order_statuses"]
    assert statuses == [
        "Bestilt ved Laserdisken",
        "Bestilt ved iMusic",
        "Bestilt ved div.",
    ]


async def test_moving_a_library_movie_to_the_wishlist_clears_its_serial_number(client):
    create = await client.post("/api/movies", json={"title": "Regretted Purchase", "media_type": "Fysisk", "format": "F-DVD"})
    movie_id = create.json()["id"]
    assert create.json()["serial_number"] is not None

    response = await client.patch(f"/api/movies/{movie_id}", json={"is_wishlist": True})
    assert response.status_code == 200
    assert response.json()["is_wishlist"] is True
    assert response.json()["serial_number"] is None
