from httpx import ASGITransport, AsyncClient

from app.main import app

# Feature #176 (Jan: "når en guest eller standart user ønske en forvisning i
# bio skal man afkraves at man også deffinere en dato og tidspunkt") —
# preferred_at is no longer optional. Every payload below now supplies one;
# see test_create_request_rejects_missing_preferred_at for the actual
# regression test of the new requirement itself.
_PREFERRED_AT = "2026-09-04T20:00:00"


async def _create_movie(client, title="Requested Movie"):
    created = await client.post("/api/movies", json={"title": title, "media_type": "Fysisk", "format": "F-DVD"})
    return created.json()["id"]


async def test_request_screening_creates_pending_request(client):
    movie_id = await _create_movie(client)
    response = await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["title"] == "Requested Movie"
    assert [r["username"] for r in data["requested_by"]] == ["testuser"]


async def test_requesting_same_movie_twice_by_same_user_is_idempotent(client):
    movie_id = await _create_movie(client)
    await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
    )
    response = await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
    )
    assert len(response.json()["requested_by"]) == 1


async def test_requesting_same_movie_by_different_users_adds_both(client):
    movie_id = await _create_movie(client)
    await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second:
        register = await second.post(
            "/api/auth/register", json={"username": "seconduser", "password": "testpassword123"}
        )
        await client.patch(
            f"/api/users/{register.json()['id']}/status", json={"status": "active"}
        )
        await second.post(
            "/api/screening-requests",
            json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
        )

    response = await client.get("/api/screening-requests")
    usernames = {r["username"] for r in response.json()[0]["requested_by"]}
    assert usernames == {"testuser", "seconduser"}


async def test_create_request_rejects_missing_reference(client):
    response = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "preferred_at": _PREFERRED_AT}
    )
    assert response.status_code == 422


async def test_create_request_rejects_missing_preferred_at(client):
    """Feature #176 — a screening request must define a date/time; a
    reference alone (matching the pre-#176 payload shape) is no longer
    enough."""
    movie_id = await _create_movie(client)
    response = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert response.status_code == 422


async def test_list_requests_requires_admin(client):
    movie_id = await _create_movie(client)
    await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/screening-requests")
        assert response.status_code == 403


async def test_mine_returns_only_current_users_pending_requests(client):
    movie_id = await _create_movie(client)
    await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
    )

    response = await client.get("/api/screening-requests/mine")
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_decline_request_requires_admin(client):
    movie_id = await _create_movie(client)
    created = await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
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
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
    )
    request_id = created.json()["id"]

    response = await client.patch(
        f"/api/screening-requests/{request_id}", json={"status": "declined"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "declined"

    # A declined request no longer blocks a fresh request for the same title.
    again = await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
    )
    assert again.json()["id"] != request_id
    assert again.json()["status"] == "pending"


async def test_request_stores_message_and_preferred_time(client):
    """Feature #85 — begge felter hører til ønskerens egen entry, ikke til
    anmodningen, så flere ønskere kan have hver sin besked/tidspunkt.
    Feature #176 — preferred_at er ikke længere valgfri, men gemmes stadig
    på nøjagtig samme måde."""
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


async def test_request_without_message_keeps_message_null(client):
    """`message` alone is still optional (feature #176 only tightened
    `preferred_at`) — omitting just the message should still behave exactly
    as before #176."""
    movie_id = await _create_movie(client)
    response = await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
    )
    entry = response.json()["requested_by"][0]
    assert entry["message"] is None
    assert entry["preferred_at"].startswith("2026-09-04T20:00")


async def test_whitespace_only_message_is_stored_as_none(client):
    """Tom og whitespace-only er samme "tomhed" — normaliseres i servicen, så
    hverken admin-panelet eller API'et skal skelne (CLAUDE.md regel 16)."""
    movie_id = await _create_movie(client)
    response = await client.post(
        "/api/screening-requests",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "message": "   ",
            "preferred_at": _PREFERRED_AT,
        },
    )
    assert response.json()["requested_by"][0]["message"] is None


async def test_second_request_from_same_user_keeps_first_message(client):
    """Dedup'en er stadig kun på username: gentagne ønsker tilføjer hverken
    en ekstra entry eller overskriver den oprindelige besked."""
    movie_id = await _create_movie(client)
    await client.post(
        "/api/screening-requests",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "message": "Første ønske",
            "preferred_at": _PREFERRED_AT,
        },
    )
    response = await client.post(
        "/api/screening-requests",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "message": "Andet forsøg",
            "preferred_at": _PREFERRED_AT,
        },
    )
    requested_by = response.json()["requested_by"]
    assert len(requested_by) == 1
    assert requested_by[0]["message"] == "Første ønske"


async def test_each_requester_keeps_their_own_message(client):
    movie_id = await _create_movie(client)
    await client.post(
        "/api/screening-requests",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "message": "Jans ønske",
            "preferred_at": "2026-09-06T18:00:00",
        },
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
    assert by_username["testuser"]["preferred_at"].startswith("2026-09-06T18:00")
    assert by_username["wishuser"]["message"] == "Annas ønske"
    assert by_username["wishuser"]["preferred_at"].startswith("2026-09-05T19:30")


async def test_message_longer_than_500_chars_is_rejected(client):
    movie_id = await _create_movie(client)
    response = await client.post(
        "/api/screening-requests",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "message": "x" * 501,
            "preferred_at": _PREFERRED_AT,
        },
    )
    assert response.status_code == 422


async def test_guest_can_request_with_message(client):
    """Feature #72's undtagelse gælder også #85/#176's felter — visnings-
    ønsket er guest-rollens ene skrivehandling, besked og tidspunkt inklusive."""
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
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "message": "Må jeg se den med?",
            "preferred_at": _PREFERRED_AT,
        },
    )
    assert response.status_code == 201
    assert response.json()["requested_by"][0]["message"] == "Må jeg se den med?"
    await guest.aclose()


async def test_screening_requests_require_authentication(raw_client):
    response = await raw_client.post(
        "/api/screening-requests",
        json={
            "media_kind": "movie",
            "movie_id": "000000000000000000000000",
            "preferred_at": _PREFERRED_AT,
        },
    )
    assert response.status_code == 401


# Feature #177 (Jan: "vi skal kunne sætte om guest ... skal bruge dato/tid
# eller ikke"), udvidet af feature #186 (Jan, 2026-08-20: "angivning af
# dato/tid for forvisning skal gælde for alle roller og ikke kun guest") —
# den admin-styrbare til/fra, nu fælles for alle roller frem for kun guest.


async def _guest_client(admin_client, username):
    transport = ASGITransport(app=app)
    guest = AsyncClient(transport=transport, base_url="http://test")
    register = await guest.post(
        "/api/auth/register", json={"username": username, "password": "testpassword123"}
    )
    user_id = register.json()["id"]
    await admin_client.patch(f"/api/users/{user_id}/status", json={"status": "active"})
    # Feature #175 gør dette redundant (guest er allerede default), men
    # eksplicit for tydelighedens skyld.
    await admin_client.patch(f"/api/users/{user_id}/role", json={"role": "guest"})
    return guest


async def _standard_client(admin_client, username):
    transport = ASGITransport(app=app)
    standard = AsyncClient(transport=transport, base_url="http://test")
    register = await standard.post(
        "/api/auth/register", json={"username": username, "password": "testpassword123"}
    )
    user_id = register.json()["id"]
    await admin_client.patch(f"/api/users/{user_id}/status", json={"status": "active"})
    await admin_client.patch(f"/api/users/{user_id}/role", json={"role": "standard"})
    return standard


async def test_preferred_at_still_required_by_default(client):
    movie_id = await _create_movie(client)
    guest = await _guest_client(client, "guestdefault177")

    response = await guest.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert response.status_code == 422
    await guest.aclose()


async def test_guest_can_omit_preferred_at_when_policy_disabled(client):
    await client.patch(
        "/api/settings/screening-request-policy",
        json={"require_preferred_at": False},
    )
    movie_id = await _create_movie(client)
    guest = await _guest_client(client, "guestexempt177")

    response = await guest.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert response.status_code == 201
    assert response.json()["requested_by"][0]["preferred_at"] is None
    await guest.aclose()


async def test_guest_can_still_supply_preferred_at_when_policy_disabled(client):
    """Turning the requirement off doesn't forbid a time — it just stops
    demanding one."""
    await client.patch(
        "/api/settings/screening-request-policy",
        json={"require_preferred_at": False},
    )
    movie_id = await _create_movie(client)
    guest = await _guest_client(client, "guestoptional177")

    response = await guest.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": _PREFERRED_AT},
    )
    assert response.status_code == 201
    assert response.json()["requested_by"][0]["preferred_at"].startswith("2026-09-04T20:00")
    await guest.aclose()


async def test_standard_and_admin_still_require_preferred_at_when_policy_enabled(client):
    """Sanity check the other direction: with the policy on (the default),
    every role is required — matches feature #176's original behaviour,
    now just via the shared policy rather than a hardcoded rule."""
    movie_id = await _create_movie(client)

    admin_response = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert admin_response.status_code == 422

    standard = await _standard_client(client, "standardstillreq186")
    standard_response = await standard.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert standard_response.status_code == 422
    await standard.aclose()


async def test_standard_and_admin_are_also_exempted_when_policy_disabled(client):
    """Feature #186 — reverses the earlier "standard/admin always required"
    rule: the policy now applies the same way to every role, not just
    guest."""
    await client.patch(
        "/api/settings/screening-request-policy",
        json={"require_preferred_at": False},
    )
    movie_id = await _create_movie(client)

    admin_response = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert admin_response.status_code == 201

    standard = await _standard_client(client, "standardexempt186")
    standard_response = await standard.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert standard_response.status_code == 201
    await standard.aclose()
