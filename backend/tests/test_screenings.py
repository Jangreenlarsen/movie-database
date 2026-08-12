from httpx import ASGITransport, AsyncClient

from app.main import app


async def _create_movie(client, title="Screening Movie"):
    created = await client.post("/api/movies", json={"title": title, "media_type": "Fysisk", "format": "DVD"})
    return created.json()["id"]


async def test_create_screening_requires_admin(client):
    movie_id = await _create_movie(client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        response = await standard_client.post(
            "/api/screenings",
            json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2026-09-01T20:00:00"},
        )
        assert response.status_code == 403


async def test_create_screening_enriches_display_info(client):
    movie_id = await _create_movie(client, title="Fredag Filmaften")
    response = await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "scheduled_at": "2026-09-01T20:00:00",
            "note": "Popcorn medbringes",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Fredag Filmaften"
    assert data["note"] == "Popcorn medbringes"
    assert data["created_by"] == "testuser"


async def test_create_screening_from_request_marks_request_scheduled(client):
    movie_id = await _create_movie(client)
    request = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    request_id = request.json()["id"]

    await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "scheduled_at": "2026-09-01T20:00:00",
            "request_id": request_id,
        },
    )

    pending = await client.get("/api/screening-requests", params={"status": "pending"})
    assert pending.json() == []

    scheduled = await client.get("/api/screening-requests", params={"status": "scheduled"})
    assert len(scheduled.json()) == 1
    assert scheduled.json()[0]["id"] == request_id


async def test_list_screenings_sorted_by_date(client):
    movie_a = await _create_movie(client, "Later Movie")
    movie_b = await _create_movie(client, "Sooner Movie")
    await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_a, "scheduled_at": "2026-09-10T20:00:00"},
    )
    await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_b, "scheduled_at": "2026-09-01T20:00:00"},
    )

    response = await client.get("/api/screenings")
    assert [s["title"] for s in response.json()] == ["Sooner Movie", "Later Movie"]


async def test_list_screenings_upcoming_filter_excludes_past(client):
    movie_id = await _create_movie(client, "Past Screening")
    await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2020-01-01T20:00:00"},
    )

    all_screenings = await client.get("/api/screenings")
    assert len(all_screenings.json()) == 1

    upcoming = await client.get("/api/screenings", params={"upcoming": "true"})
    assert upcoming.json() == []


async def test_list_screenings_past_filter_returns_history_newest_first(client):
    """Feature #130 — historik-visningen under Settings: kun afholdte
    fremvisninger, nyeste øverst."""
    old_id = await _create_movie(client, "Ældst")
    newer_id = await _create_movie(client, "Nyere")
    future_id = await _create_movie(client, "Fremtid")
    await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": old_id, "scheduled_at": "2020-01-01T20:00:00"},
    )
    await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": newer_id, "scheduled_at": "2021-06-15T20:00:00"},
    )
    await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": future_id, "scheduled_at": "2099-01-01T20:00:00"},
    )

    past = await client.get("/api/screenings", params={"past": "true"})
    titles = [s["title"] for s in past.json()]
    # Kun de to afholdte, nyeste først — den fremtidige er ikke med.
    assert titles == ["Nyere", "Ældst"]


async def test_update_screening_requires_admin(client):
    movie_id = await _create_movie(client)
    created = await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2026-09-01T20:00:00"},
    )
    screening_id = created.json()["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin2", "password": "testpassword123"}
        )
        response = await standard_client.patch(
            f"/api/screenings/{screening_id}", json={"note": "hacked"}
        )
        assert response.status_code == 403


async def test_update_screening_changes_time_and_note(client):
    movie_id = await _create_movie(client)
    created = await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2026-09-01T20:00:00"},
    )
    screening_id = created.json()["id"]

    response = await client.patch(
        f"/api/screenings/{screening_id}",
        json={"scheduled_at": "2026-09-02T21:00:00", "note": "Flyttet en dag"},
    )
    assert response.status_code == 200
    assert response.json()["note"] == "Flyttet en dag"
    assert response.json()["scheduled_at"].startswith("2026-09-02T21:00:00")


async def test_updated_screening_still_matches_upcoming_filter(client):
    """Regression test (BUGS.md #33): `update_screening` used to dump the
    payload with `mode="json"`, turning `scheduled_at` into an ISO string
    before the raw `$set` — corrupting its BSON type so the `upcoming_only`
    filter's `$gte` datetime comparison no longer matched it, and an edited
    screening silently vanished from the Voldby BIO front page.

    NOTE: mongomock does NOT reproduce this — its `$gte` comparison between
    a string and a `datetime` is more lenient than real MongoDB's, so this
    test passes even with the bug reverted (verified by hand). It's kept as
    documentation/a basic sanity check; the actual fix was confirmed live
    against real MongoDB via Playwright, per CLAUDE.md's runtime-context
    testing lesson (regel 16)."""
    movie_id = await _create_movie(client)
    created = await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2026-09-01T20:00:00"},
    )
    screening_id = created.json()["id"]

    await client.patch(f"/api/screenings/{screening_id}", json={"note": "Bare en note"})

    upcoming = await client.get("/api/screenings", params={"upcoming": "true"})
    assert [s["id"] for s in upcoming.json()] == [screening_id]


async def test_delete_screening_requires_admin(client):
    movie_id = await _create_movie(client)
    created = await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2026-09-01T20:00:00"},
    )
    screening_id = created.json()["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin3", "password": "testpassword123"}
        )
        response = await standard_client.delete(f"/api/screenings/{screening_id}")
        assert response.status_code == 403


async def test_delete_screening_removes_it(client):
    movie_id = await _create_movie(client)
    created = await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2026-09-01T20:00:00"},
    )
    screening_id = created.json()["id"]

    response = await client.delete(f"/api/screenings/{screening_id}")
    assert response.status_code == 204

    assert (await client.get("/api/screenings")).json() == []


async def test_delete_unknown_screening_returns_404(client):
    response = await client.delete("/api/screenings/000000000000000000000000")
    assert response.status_code == 404


async def test_screenings_list_is_public(raw_client):
    """Regression test for feature #70 — the public /bio page must be able
    to fetch the program without being logged in at all."""
    response = await raw_client.get("/api/screenings")
    assert response.status_code == 200


async def test_creating_a_screening_still_requires_authentication(raw_client):
    """Only the GET became public (feature #70) — writes are unaffected."""
    response = await raw_client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": "000000000000000000000000", "scheduled_at": "2026-09-01T20:00:00"},
    )
    assert response.status_code == 401
