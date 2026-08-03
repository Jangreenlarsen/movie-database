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
        register = await standard_client.post(
            "/api/auth/register", json={"username": "readonly", "password": "testpassword123"}
        )
        await client.patch(
            f"/api/users/{register.json()['id']}/status", json={"status": "active"}
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


async def test_update_role_of_unknown_user_returns_404(client):
    """Regression test for BUGS.md #3."""
    response = await client.patch(
        "/api/users/000000000000000000000000/role", json={"role": "admin"}
    )
    assert response.status_code == 404


async def test_cannot_demote_the_last_admin(client):
    """Regression test for BUGS.md #4. The `client` fixture's user is the
    only admin in a fresh test database."""
    me = await client.get("/api/users/me")
    my_id = me.json()["id"]

    response = await client.patch(f"/api/users/{my_id}/role", json={"role": "standard"})
    assert response.status_code == 409

    still_admin = await client.get("/api/users/me")
    assert still_admin.json()["role"] == "admin"


async def test_can_demote_an_admin_when_another_admin_remains(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second_client:
        register_response = await second_client.post(
            "/api/auth/register",
            json={"username": "secondadmin", "password": "testpassword123"},
        )
        second_id = register_response.json()["id"]

    promote = await client.patch(f"/api/users/{second_id}/role", json={"role": "admin"})
    assert promote.status_code == 200

    demote = await client.patch(f"/api/users/{second_id}/role", json={"role": "standard"})
    assert demote.status_code == 200
    assert demote.json()["role"] == "standard"


async def test_password_over_72_bytes_rejected(raw_client):
    """Regression test for BUGS.md #12 — bcrypt's real limit, not the
    128-character Pydantic ceiling."""
    response = await raw_client.post(
        "/api/auth/register",
        json={"username": "longpassworduser", "password": "x" * 73},
    )
    assert response.status_code == 422
