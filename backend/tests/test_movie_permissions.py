from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_new_movie_records_registrant_and_defaults_owner(client):
    response = await client.post("/api/movies", json={"title": "Registered Movie", "media_type": "Fysisk", "format": "F-DVD"})
    movie = response.json()
    assert movie["registered_by"] == "testuser"
    assert movie["owner"] == "testuser"


async def test_owner_and_location_can_be_set_explicitly(client):
    response = await client.post(
        "/api/movies",
        json={"title": "Shelf Movie", "location": "Stuen", "owner": "anna", "media_type": "Fysisk", "format": "F-DVD"},
    )
    movie = response.json()
    assert movie["location"] == "Stuen"
    assert movie["owner"] == "anna"
    assert movie["registered_by"] == "testuser"


async def test_standard_user_can_edit_serial_number_of_own_registered_movie(client):
    """Regression test for FEATURES.md #26 — the user who registered a movie
    may renumber it even without admin rights."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        register = await standard_client.post(
            "/api/auth/register", json={"username": "registrant", "password": "testpassword123"}
        )
        # Feature #66 — a freshly registered user is `pending` by default and
        # blocked until an admin approves them. Feature #175 — and now
        # defaults to guest (read-only) once approved, so this test (about
        # the standard role specifically) promotes explicitly.
        await client.patch(
            f"/api/users/{register.json()['id']}/status", json={"status": "active"}
        )
        await client.patch(
            f"/api/users/{register.json()['id']}/role", json={"role": "standard"}
        )
        create = await standard_client.post("/api/movies", json={"title": "Own Movie", "media_type": "Fysisk", "format": "F-DVD"})
        movie_id = create.json()["id"]

        response = await standard_client.patch(
            f"/api/movies/{movie_id}", json={"serial_number": 999}
        )
        assert response.status_code == 200
        assert response.json()["serial_number"] == 999


async def test_standard_user_cannot_edit_serial_number_of_others_movie(client):
    create = await client.post("/api/movies", json={"title": "Admin's Movie", "media_type": "Fysisk", "format": "F-DVD"})
    movie_id = create.json()["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "outsider", "password": "testpassword123"}
        )
        response = await standard_client.patch(
            f"/api/movies/{movie_id}", json={"serial_number": 555}
        )
        assert response.status_code == 403


async def test_admin_can_edit_serial_number_of_any_movie(client):
    """The `client` fixture's user is always admin (first registered user)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        register = await standard_client.post(
            "/api/auth/register", json={"username": "someoneelse", "password": "testpassword123"}
        )
        await client.patch(
            f"/api/users/{register.json()['id']}/status", json={"status": "active"}
        )
        # Feature #175 — registration now defaults to guest; this user needs
        # to actually create a (non-wishlist) library entry below.
        await client.patch(
            f"/api/users/{register.json()['id']}/role", json={"role": "standard"}
        )
        create = await standard_client.post(
            "/api/movies", json={"title": "Someone Else's Movie", "media_type": "Fysisk", "format": "F-DVD"}
        )
        movie_id = create.json()["id"]

    response = await client.patch(f"/api/movies/{movie_id}", json={"serial_number": 777})
    assert response.status_code == 200
