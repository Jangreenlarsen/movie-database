from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_first_registered_user_is_admin(raw_client):
    response = await raw_client.post(
        "/api/auth/register", json={"username": "first", "password": "testpassword123"}
    )
    assert response.json()["role"] == "admin"


async def test_second_registered_user_is_standard(raw_client):
    await raw_client.post(
        "/api/auth/register", json={"username": "first", "password": "testpassword123"}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second_client:
        response = await second_client.post(
            "/api/auth/register", json={"username": "second", "password": "testpassword123"}
        )
        assert response.json()["role"] == "standard"


async def test_admin_can_update_serial_number_config(client):
    """The `client` fixture's user is always the first-ever registered user
    in a fresh test database, so it is always admin."""
    response = await client.patch("/api/settings/serial-number", json={"start_number": 50})
    assert response.status_code == 200


async def test_standard_user_cannot_update_serial_number_config(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register",
            json={"username": "standarduser", "password": "testpassword123"},
        )
        response = await standard_client.patch(
            "/api/settings/serial-number", json={"start_number": 50}
        )
        assert response.status_code == 403


async def test_standard_user_can_still_read_serial_number_config(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "readonly", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/settings/serial-number")
        assert response.status_code == 200


async def test_change_password_with_correct_current_password(client):
    response = await client.post(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "newpassword456"},
    )
    assert response.status_code == 204

    await client.post("/api/auth/logout")
    login = await client.post(
        "/api/auth/login", json={"username": "testuser", "password": "newpassword456"}
    )
    assert login.status_code == 200


async def test_change_password_rejects_wrong_current_password(client):
    response = await client.post(
        "/api/users/me/password",
        json={"current_password": "wrongpassword", "new_password": "newpassword456"},
    )
    assert response.status_code == 401


async def test_admin_can_list_users_and_change_role(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second_client:
        register_response = await second_client.post(
            "/api/auth/register",
            json={"username": "promoteme", "password": "testpassword123"},
        )
        user_id = register_response.json()["id"]

    listing = await client.get("/api/users")
    assert listing.status_code == 200
    usernames = [u["username"] for u in listing.json()]
    assert "promoteme" in usernames

    promote = await client.patch(f"/api/users/{user_id}/role", json={"role": "admin"})
    assert promote.status_code == 200
    assert promote.json()["role"] == "admin"


async def test_standard_user_cannot_list_users(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/users")
        assert response.status_code == 403
