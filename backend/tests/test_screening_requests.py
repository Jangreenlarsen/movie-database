from httpx import ASGITransport, AsyncClient

from app.main import app


async def _create_movie(client, title="Requested Movie"):
    created = await client.post("/api/movies", json={"title": title, "media_type": "Fysisk", "format": "F-DVD"})
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
        register = await second.post(
            "/api/auth/register", json={"username": "seconduser", "password": "testpassword123"}
        )
        await client.patch(
            f"/api/users/{register.json()['id']}/status", json={"status": "active"}
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


async def test_request_stores_message_and_preferred_time(client):
    """Feature #85 — begge felter hører til ønskerens egen entry, ikke til
    anmodningen, så flere ønskere kan have hver sin besked/tidspunkt."""
    movie_id = await _create_movie(client)
    response = await client.post(
        "/api/screening-requests",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "message": "Gerne en fredag aften",
            "preferred_at": "2026-09-04T20:00:00",
        },
    )
    assert response.status_code == 201
    entry = response.json()["requested_by"][0]
    assert entry["message"] == "Gerne en fredag aften"
    assert entry["preferred_at"].startswith("2026-09-04T20:00")


async def test_request_without_message_keeps_fields_null(client):
    """Pre-#85 payload-formen skal opføre sig præcis som før."""
    movie_id = await _create_movie(client)
    response = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    entry = response.json()["requested_by"][0]
    assert entry["message"] is None
    assert entry["preferred_at"] is None


async def test_whitespace_only_message_is_stored_as_none(client):
    """Tom og whitespace-only er samme "tomhed" — normaliseres i servicen, så
    hverken admin-panelet eller API'et skal skelne (CLAUDE.md regel 16)."""
    movie_id = await _create_movie(client)
    response = await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "message": "   "},
    )
    assert response.json()["requested_by"][0]["message"] is None


async def test_second_request_from_same_user_keeps_first_message(client):
    """Dedup'en er stadig kun på username: gentagne ønsker tilføjer hverken
    en ekstra entry eller overskriver den oprindelige besked."""
    movie_id = await _create_movie(client)
    await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "message": "Første ønske"},
    )
    response = await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "message": "Andet forsøg"},
    )
    requested_by = response.json()["requested_by"]
    assert len(requested_by) == 1
    assert requested_by[0]["message"] == "Første ønske"


async def test_each_requester_keeps_their_own_message(client):
    movie_id = await _create_movie(client)
    await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "message": "Jans ønske"},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second:
        register = await second.post(
            "/api/auth/register", json={"username": "wishuser", "password": "testpassword123"}
        )
        await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})
        await second.post(
            "/api/screening-requests",
            json={
                "media_kind": "movie",
                "movie_id": movie_id,
                "message": "Annas ønske",
                "preferred_at": "2026-09-05T19:30:00",
            },
        )

    response = await client.get("/api/screening-requests")
    by_username = {r["username"]: r for r in response.json()[0]["requested_by"]}
    assert by_username["testuser"]["message"] == "Jans ønske"
    assert by_username["testuser"]["preferred_at"] is None
    assert by_username["wishuser"]["message"] == "Annas ønske"
    assert by_username["wishuser"]["preferred_at"].startswith("2026-09-05T19:30")


async def test_message_longer_than_500_chars_is_rejected(client):
    movie_id = await _create_movie(client)
    response = await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "message": "x" * 501},
    )
    assert response.status_code == 422


async def test_guest_can_request_with_message(client):
    """Feature #72's undtagelse gælder også #85's felter — visnings-ønsket er
    guest-rollens ene skrivehandling, besked inklusive."""
    movie_id = await _create_movie(client)

    transport = ASGITransport(app=app)
    guest = AsyncClient(transport=transport, base_url="http://test")
    register = await guest.post(
        "/api/auth/register", json={"username": "guestwisher", "password": "testpassword123"}
    )
    user_id = register.json()["id"]
    await client.patch(f"/api/users/{user_id}/status", json={"status": "active"})
    await client.patch(f"/api/users/{user_id}/role", json={"role": "guest"})

    response = await guest.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "message": "Må jeg se den med?"},
    )
    assert response.status_code == 201
    assert response.json()["requested_by"][0]["message"] == "Må jeg se den med?"
    await guest.aclose()


async def test_screening_requests_require_authentication(raw_client):
    response = await raw_client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": "000000000000000000000000"}
    )
    assert response.status_code == 401
