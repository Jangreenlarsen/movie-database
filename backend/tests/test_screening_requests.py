from httpx import ASGITransport, AsyncClient

from app.main import app


async def _create_movie(client, title="Requested Movie"):
    created = await client.post("/api/movies", json={"title": title})
    return created.json()["id"]


async def test_request_screening_creates_pending_request(client):
    movie_id = await _create_movie(client)
    response = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["title"] == "Requested Movie"
    assert [r["username"] for r in data["requested_by"]] == ["testuser"]


async def test_requesting_same_movie_twice_by_same_user_is_idempotent(client):
    movie_id = await _create_movie(client)
    await client.post("/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id})
    response = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert len(response.json()["requested_by"]) == 1


async def test_requesting_same_movie_by_different_users_adds_both(client):
    movie_id = await _create_movie(client)
    await client.post("/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second:
        await second.post(
            "/api/auth/register", json={"username": "seconduser", "password": "testpassword123"}
        )
        await second.post("/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id})

    response = await client.get("/api/screening-requests")
    usernames = {r["username"] for r in response.json()[0]["requested_by"]}
    assert usernames == {"testuser", "seconduser"}


async def test_create_request_rejects_missing_reference(client):
    response = await client.post("/api/screening-requests", json={"media_kind": "movie"})
    assert response.status_code == 422


async def test_list_requests_requires_admin(client):
    movie_id = await _create_movie(client)
    await client.post("/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/screening-requests")
        assert response.status_code == 403


async def test_mine_returns_only_current_users_pending_requests(client):
    movie_id = await _create_movie(client)
    await client.post("/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id})

    response = await client.get("/api/screening-requests/mine")
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_decline_request_requires_admin(client):
    movie_id = await _create_movie(client)
    created = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    request_id = created.json()["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin2", "password": "testpassword123"}
        )
        response = await standard_client.patch(
            f"/api/screening-requests/{request_id}", json={"status": "declined"}
        )
        assert response.status_code == 403


async def test_decline_request_marks_status_declined(client):
    movie_id = await _create_movie(client)
    created = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    request_id = created.json()["id"]

    response = await client.patch(
        f"/api/screening-requests/{request_id}", json={"status": "declined"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "declined"

    # A declined request no longer blocks a fresh request for the same title.
    again = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert again.json()["id"] != request_id
    assert again.json()["status"] == "pending"


async def test_screening_requests_require_authentication(raw_client):
    response = await raw_client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": "000000000000000000000000"}
    )
    assert response.status_code == 401
