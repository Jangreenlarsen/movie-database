"""Regression tests for the 2026-08-05 two-phase review (BUGS.md #40-#46).

Each test here reproduces the exact scenario that the review's phase-2 probe
tests demonstrated was broken, so a future change that reintroduces any of
them fails loudly instead of silently.
"""

import asyncio

from bson import ObjectId

from app.core.errors import InvalidBackupError
from app.models.backup import SystemBackup
from app.repositories import user_repository
from app.services import screening_service, system_backup_service


async def _login(client, username, password="testpassword123"):
    return await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


async def _register_and_return_as_admin(client, username, admin_username="testuser"):
    """Registering logs the new account in (the endpoint sets the cookie), so
    every helper here logs back in as the admin afterwards."""
    await client.post(
        "/api/auth/register", json={"username": username, "password": "testpassword123"}
    )
    await _login(client, admin_username)


# --------------------------------------------------------------------------
# BUGS.md #40 — last ACTIVE admin must never be demotable
# --------------------------------------------------------------------------


async def test_cannot_demote_the_last_active_admin_when_a_disabled_admin_exists(client, db):
    """The exact reproduction from the review: a *disabled* admin used to
    satisfy the status-blind `count_by_role` guard, so the only admin who
    could still log in could be demoted — an unrecoverable lockout."""
    await _register_and_return_as_admin(client, "adminb")

    users = (await client.get("/api/users")).json()
    b = next(u for u in users if u["username"] == "adminb")
    a = next(u for u in users if u["username"] == "testuser")

    await client.patch(f"/api/users/{b['id']}/status", json={"status": "active"})
    await client.patch(f"/api/users/{b['id']}/role", json={"role": "admin"})
    await client.patch(f"/api/users/{b['id']}/status", json={"status": "disabled"})
    assert await user_repository.count_active_admins(db) == 1

    response = await client.patch(f"/api/users/{a['id']}/role", json={"role": "standard"})
    assert response.status_code == 409
    assert await user_repository.count_active_admins(db) == 1
    # And the admin surface is still reachable — no lockout.
    assert (await client.get("/api/users")).status_code == 200


async def test_cannot_demote_the_last_active_admin_when_a_pending_admin_exists(client, db):
    """Same guard, other non-active status: a pending account promoted to
    admin (possible via the API) must not count as a usable spare either."""
    await _register_and_return_as_admin(client, "pendingadmin")

    users = (await client.get("/api/users")).json()
    pending = next(u for u in users if u["username"] == "pendingadmin")
    a = next(u for u in users if u["username"] == "testuser")
    assert pending["status"] == "pending"

    await client.patch(f"/api/users/{pending['id']}/role", json={"role": "admin"})

    response = await client.patch(f"/api/users/{a['id']}/role", json={"role": "standard"})
    assert response.status_code == 409
    assert await user_repository.count_active_admins(db) == 1


async def test_demoting_a_non_active_admin_is_still_allowed(client, db):
    """The guard must not over-correct: demoting a disabled admin can't
    reduce the number of admins who can actually log in, so it stays legal."""
    await _register_and_return_as_admin(client, "adminb")

    users = (await client.get("/api/users")).json()
    b = next(u for u in users if u["username"] == "adminb")
    await client.patch(f"/api/users/{b['id']}/status", json={"status": "active"})
    await client.patch(f"/api/users/{b['id']}/role", json={"role": "admin"})
    await client.patch(f"/api/users/{b['id']}/status", json={"status": "disabled"})

    response = await client.patch(f"/api/users/{b['id']}/role", json={"role": "standard"})
    assert response.status_code == 200
    assert response.json()["role"] == "standard"


async def test_can_still_demote_an_admin_when_another_active_admin_remains(client, db):
    """Baseline: the guard only fires for the *last* active admin."""
    await _register_and_return_as_admin(client, "adminb")

    users = (await client.get("/api/users")).json()
    b = next(u for u in users if u["username"] == "adminb")
    await client.patch(f"/api/users/{b['id']}/status", json={"status": "active"})
    await client.patch(f"/api/users/{b['id']}/role", json={"role": "admin"})
    assert await user_repository.count_active_admins(db) == 2

    response = await client.patch(f"/api/users/{b['id']}/role", json={"role": "standard"})
    assert response.status_code == 200


# --------------------------------------------------------------------------
# BUGS.md #41 — a restore payload must not be able to wipe everything
# --------------------------------------------------------------------------


async def test_restore_with_no_collections_is_rejected_and_deletes_nothing(client, db):
    """Every SystemBackup list defaults to [], so a truncated/wrong file used
    to validate cleanly and then delete every collection, returning 200."""
    await client.post("/api/movies", json={"title": "Keep Me", "media_type": "Fysisk", "format": "DVD"})
    users_before = await db["users"].count_documents({})
    movies_before = await db["movies"].count_documents({})

    response = await client.post(
        "/api/system/restore",
        json={"backed_up_at": "2026-08-05T00:00:00Z", "app_version": "0.59.0"},
    )

    assert response.status_code == 400
    assert "aktiv admin" in response.json()["detail"]
    # Crucially: nothing was destroyed on the way to that error.
    assert await db["users"].count_documents({}) == users_before
    assert await db["movies"].count_documents({}) == movies_before


async def test_restore_is_rejected_when_backup_has_no_active_admin(client, db):
    """Subtler variant: users are present, but none of them could administer
    (or undo) the restored system."""
    await client.post("/api/movies", json={"title": "Keep Me", "media_type": "Fysisk", "format": "DVD"})
    movies_before = await db["movies"].count_documents({})

    response = await client.post(
        "/api/system/restore",
        json={
            "backed_up_at": "2026-08-05T00:00:00Z",
            "app_version": "0.59.0",
            "users": [
                {"username": "someone", "role": "standard", "status": "active"},
                {"username": "oldadmin", "role": "admin", "status": "disabled"},
            ],
        },
    )

    assert response.status_code == 400
    assert await db["movies"].count_documents({}) == movies_before


async def test_restore_accepts_a_genuine_backup(client, db):
    """A real snapshot always contains the active admin who took it, so the
    new guard must not get in the way of the feature working."""
    await client.post("/api/movies", json={"title": "Original", "media_type": "Fysisk", "format": "DVD"})
    backup = (await client.get("/api/system/backup")).json()

    await client.post("/api/movies", json={"title": "Added After Backup", "media_type": "Fysisk", "format": "DVD"})
    assert await db["movies"].count_documents({}) == 2

    response = await client.post("/api/system/restore", json=backup)
    assert response.status_code == 200
    assert response.json()["movies_imported"] == 1
    assert await db["movies"].count_documents({}) == 1


async def test_restore_of_an_empty_library_is_still_allowed(client, db):
    """An empty *library* is legitimate (a backup taken before any films were
    added) — only the missing-admin case is rejected."""
    await client.post("/api/movies", json={"title": "Will Be Replaced", "media_type": "Fysisk", "format": "DVD"})
    admin = await db["users"].find_one({"username": "testuser"})

    backup = SystemBackup(
        backed_up_at="2026-08-05T00:00:00Z",
        app_version="0.59.0",
        users=[{**admin, "_id": str(admin["_id"])}],
    )
    result = await system_backup_service.restore_backup(db, backup)

    assert result.movies_imported == 0
    assert await db["movies"].count_documents({}) == 0
    assert await user_repository.count_active_admins(db) == 1


async def test_assert_restorable_raises_before_any_deletion():
    """Unit-level guarantee that validation happens up front."""
    backup = SystemBackup(backed_up_at="2026-08-05T00:00:00Z", app_version="0.59.0")
    try:
        system_backup_service._assert_restorable(backup)
    except InvalidBackupError:
        return
    raise AssertionError("expected InvalidBackupError")


# --------------------------------------------------------------------------
# BUGS.md #42 — no orphan screening when request_id is invalid
# --------------------------------------------------------------------------


async def test_scheduling_against_an_unknown_request_creates_no_screening(client, db):
    movie = (await client.post("/api/movies", json={"title": "Probe Movie", "media_type": "Fysisk", "format": "DVD"})).json()

    response = await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie["id"],
            "scheduled_at": "2030-01-01T20:00:00Z",
            "request_id": str(ObjectId()),
        },
    )

    assert response.status_code == 404
    assert await db["screenings"].count_documents({}) == 0


async def test_scheduling_from_a_real_request_still_works(client, db):
    """The reordering must not break the normal path: the screening is
    created and the originating request is marked scheduled."""
    movie = (await client.post("/api/movies", json={"title": "Probe Movie", "media_type": "Fysisk", "format": "DVD"})).json()
    request = (
        await client.post(
            "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie["id"]}
        )
    ).json()

    response = await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie["id"],
            "scheduled_at": "2030-01-01T20:00:00Z",
            "request_id": request["id"],
        },
    )

    assert response.status_code == 201
    assert await db["screenings"].count_documents({}) == 1
    stored = await db["screening_requests"].find_one({"_id": ObjectId(request["id"])})
    assert stored["status"] == "scheduled"


# --------------------------------------------------------------------------
# BUGS.md #43 — deleting a title cleans up its screenings/requests
# --------------------------------------------------------------------------


async def test_deleting_a_movie_removes_its_screenings_and_requests(client, db):
    movie = (await client.post("/api/movies", json={"title": "Probe Movie", "media_type": "Fysisk", "format": "DVD"})).json()
    await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie["id"],
            "scheduled_at": "2030-01-01T20:00:00Z",
        },
    )
    await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie["id"]}
    )
    assert await db["screenings"].count_documents({}) == 1

    await client.delete(f"/api/movies/{movie['id']}")

    assert await db["screenings"].count_documents({}) == 0
    assert await db["screening_requests"].count_documents({}) == 0
    assert (await client.get("/api/screenings")).json() == []


async def test_deleting_a_tv_show_removes_its_screenings_and_requests(client, db, monkeypatch):
    from app.integrations import tmdb_client

    from tests.test_tv_shows import _fake_tv_details

    async def fake_details(tv_id):
        return _fake_tv_details(tv_id)

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_details)
    show = (await client.post("/api/tv-shows", json={"tmdb_id": 1409, "media_type": "Fysisk", "format": "DVD"})).json()

    await client.post(
        "/api/screenings",
        json={
            "media_kind": "tv",
            "tv_show_id": show["id"],
            "scheduled_at": "2030-01-01T20:00:00Z",
        },
    )
    await client.post(
        "/api/screening-requests", json={"media_kind": "tv", "tv_show_id": show["id"]}
    )
    assert await db["screenings"].count_documents({}) == 1

    await client.delete(f"/api/tv-shows/{show['id']}")

    assert await db["screenings"].count_documents({}) == 0
    assert await db["screening_requests"].count_documents({}) == 0


async def test_deleting_a_movie_leaves_other_titles_screenings_alone(client, db):
    """The cleanup must be scoped to the deleted title only."""
    keep = (await client.post("/api/movies", json={"title": "Keep", "media_type": "Fysisk", "format": "DVD"})).json()
    drop = (await client.post("/api/movies", json={"title": "Drop", "media_type": "Fysisk", "format": "DVD"})).json()
    for movie_id in (keep["id"], drop["id"]):
        await client.post(
            "/api/screenings",
            json={
                "media_kind": "movie",
                "movie_id": movie_id,
                "scheduled_at": "2030-01-01T20:00:00Z",
            },
        )

    await client.delete(f"/api/movies/{drop['id']}")

    remaining = await db["screenings"].find({}).to_list(length=None)
    assert len(remaining) == 1
    assert remaining[0]["movie_id"] == keep["id"]


# --------------------------------------------------------------------------
# BUGS.md #44 — concurrent requests for one title yield one shared request
# --------------------------------------------------------------------------


async def test_concurrent_requests_for_the_same_title_share_one_request(client, db):
    movie = (await client.post("/api/movies", json={"title": "Probe Movie", "media_type": "Fysisk", "format": "DVD"})).json()

    await asyncio.gather(
        screening_service.request_screening(db, "movie", movie["id"], None, "userA"),
        screening_service.request_screening(db, "movie", movie["id"], None, "userB"),
    )

    docs = await db["screening_requests"].find({}).to_list(length=None)
    assert len(docs) == 1
    assert {r["username"] for r in docs[0]["requested_by"]} == {"userA", "userB"}


async def test_a_title_can_be_requested_again_after_being_declined(client, db):
    """The pending-only partial index must not block the legitimate history
    of several declined requests for the same title."""
    movie = (await client.post("/api/movies", json={"title": "Probe Movie", "media_type": "Fysisk", "format": "DVD"})).json()

    first = (
        await client.post(
            "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie["id"]}
        )
    ).json()
    await client.patch(f"/api/screening-requests/{first['id']}", json={"status": "declined"})

    second = await client.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie["id"]}
    )
    assert second.status_code == 201
    assert second.json()["id"] != first["id"]

    declined_again = await client.patch(
        f"/api/screening-requests/{second.json()['id']}", json={"status": "declined"}
    )
    assert declined_again.status_code == 200
    assert await db["screening_requests"].count_documents({"status": "declined"}) == 2


# --------------------------------------------------------------------------
# BUGS.md #46 — guest restrictions enforced server-side
# --------------------------------------------------------------------------


async def test_guest_cannot_read_stats_or_deleted_movies(client, db):
    await _register_and_return_as_admin(client, "guestuser")
    users = (await client.get("/api/users")).json()
    guest = next(u for u in users if u["username"] == "guestuser")
    await client.patch(f"/api/users/{guest['id']}/status", json={"status": "active"})
    await client.patch(f"/api/users/{guest['id']}/role", json={"role": "guest"})

    await _login(client, "guestuser")

    assert (await client.get("/api/movies/stats")).status_code == 403
    assert (await client.get("/api/movies/deleted")).status_code == 403
    # ...but the library itself stays readable, which is the whole point of
    # the guest role.
    assert (await client.get("/api/movies")).status_code == 200


async def test_standard_user_can_still_read_stats_and_deleted_movies(client):
    await _register_and_return_as_admin(client, "standarduser")
    users = (await client.get("/api/users")).json()
    standard = next(u for u in users if u["username"] == "standarduser")
    await client.patch(f"/api/users/{standard['id']}/status", json={"status": "active"})

    await _login(client, "standarduser")

    assert (await client.get("/api/movies/stats")).status_code == 200
    assert (await client.get("/api/movies/deleted")).status_code == 200
