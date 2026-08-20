from httpx import ASGITransport, AsyncClient

from app.integrations import tmdb_client
from app.main import app


async def test_backup_includes_all_expected_collections(client, monkeypatch):
    async def fake_fetch(size, path):
        return b"fake-poster-bytes", "image/jpeg"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)
    # Feature #153 — varmer poster_cache op med præcis én post via den
    # offentlige endpoint, samme måde en rigtig browser ville.
    await client.get("/api/posters/w185/backup-test.jpg")

    await client.post("/api/movies", json={"title": "Backup Movie", "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/tv-shows", json={"name": "Backup Show", "media_type": "Fysisk", "format": "F-DVD"})
    created = await client.post("/api/movies", json={"title": "Deleted Movie", "media_type": "Fysisk", "format": "F-DVD"})
    await client.delete(f"/api/movies/{created.json()['id']}")

    # BUGS.md #65 — screenings/screening_requests/seat_reservations/messages/
    # audit_log/visits were silently missing from the backup entirely; a
    # regression test needs actual rows in each to prove they now come back.
    movie_for_screening = await client.post(
        "/api/movies", json={"title": "Screening Movie", "media_type": "Fysisk", "format": "F-DVD"}
    )
    movie_id = movie_for_screening.json()["id"]
    await client.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2026-09-04T20:00:00"},
    )
    await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2026-09-01T20:00:00"},
    )
    await client.post("/api/reservations/hold", json={"seat_id": "N1-1", "scope": "global"})
    # A broadcast message excludes its own sender from the recipient list
    # (message_service._resolve_recipients), so a second active user is
    # needed or there'd be nobody to receive it (409 NoRecipientsError).
    # Registered through a *separate* client — registering through `client`
    # itself would log it in as the new (non-admin) user, demoting every
    # later admin-only call in this test to a 403.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as recipient_client:
        recipient = await recipient_client.post(
            "/api/auth/register", json={"username": "backuprecipient", "password": "testpassword123"}
        )
    await client.patch(f"/api/users/{recipient.json()['id']}/status", json={"status": "active"})
    await client.post("/api/messages", json={"subject": "Hej", "body": "Test", "recipient_user_id": None})
    await client.post("/api/analytics/visit", json={"page": "library"})

    response = await client.get("/api/system/backup")
    assert response.status_code == 200
    data = response.json()

    assert len(data["movies"]) == 2
    assert len(data["tv_shows"]) == 1
    assert len(data["deleted_movies"]) == 1
    assert len(data["users"]) == 2
    assert len(data["counters"]) >= 1
    assert len(data["screenings"]) == 1
    assert len(data["screening_requests"]) == 1
    assert len(data["seat_reservations"]) == 1
    assert len(data["messages"]) == 1
    # Creating the screening + the screening-request above are themselves
    # audit-logged actions, so the audit trail is non-empty here too.
    assert len(data["audit_log"]) >= 2
    assert len(data["visits"]) == 1
    assert len(data["poster_cache"]) == 1
    assert "backed_up_at" in data
    assert "app_version" in data
    # system_settings must never appear anywhere in the backup — the whole
    # point of excluding it (CLAUDE.md regel 6 / FEATURES.md #61).
    assert "system_settings" not in data
    # 2026-08-15 sync audit — the non-secret keys ARE captured, always all
    # present ("" meaning "no override"), unlike the excluded whole.
    # Feature #178 added plex_shield_client_identifier to the same set.
    # Feature #183 added anthem_host/anthem_port — anthem_port is always its
    # actual effective value (never ""), since an int has no meaningful
    # "cleared" empty-string sentinel the way the string fields do.
    assert data["system_settings_plain"] == {
        "plex_server_url": "",
        "primary_barcode_source": "",
        "plex_shield_client_identifier": "",
        "anthem_host": "",
        "anthem_port": 14999,
    }
    # Feature #174 — den nyeste tilføjelse til samme system_settings-
    # dokument, checket ind fra dag ét i stedet for at blive opdaget
    # manglende bagefter (regel 20 anvendt proaktivt).
    assert data["password_policy"] == {
        "password_min_length": 8,
        "password_require_uppercase": False,
        "password_require_lowercase": False,
        "password_require_digit": False,
    }


async def test_backup_never_exposes_api_keys(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "tmdb_api_token", "super-secret-tmdb-token")
    response = await client.get("/api/system/backup")
    assert "super-secret-tmdb-token" not in response.text


async def test_backup_includes_plain_settings_but_never_secret_ones(client):
    # A plain (non-secret) override and a secret override, set together.
    await client.patch(
        "/api/settings/system",
        json={"plex_server_url": "http://plex.local:32400", "tmdb_api_token": "super-secret-token"},
    )

    response = await client.get("/api/system/backup")
    data = response.json()

    assert data["system_settings_plain"] == {
        "plex_server_url": "http://plex.local:32400",
        "primary_barcode_source": "",
        "plex_shield_client_identifier": "",
        "anthem_host": "",
        "anthem_port": 14999,
    }
    assert "super-secret-token" not in response.text
    assert "tmdb_api_token" not in data["system_settings_plain"]


async def test_restore_reapplies_plain_settings_without_touching_secrets(client):
    await client.patch(
        "/api/settings/system",
        json={"plex_server_url": "http://plex.local:32400", "tmdb_api_token": "super-secret-token"},
    )
    backup = (await client.get("/api/system/backup")).json()

    # Changed after the backup was taken — restore should bring back the
    # backed-up value, exactly like every other wholesale-replaced collection.
    await client.patch("/api/settings/system", json={"plex_server_url": "http://changed.local:32400"})

    response = await client.post("/api/system/restore", json=backup)
    assert response.status_code == 200
    result = response.json()
    # 2: plex_server_url (customized) + anthem_port (feature #183 — always
    # truthy, since its code default 14999 counts as "present" even when
    # never customized; see the snapshot comment in system_backup_service).
    assert result["system_settings_plain_restored"] == 2

    status = (await client.get("/api/settings/system")).json()
    assert status["plex_server_url"] == "http://plex.local:32400"
    # The secret set alongside it survived too — restore never touches
    # system_settings wholesale, so it was never at risk, but confirm it
    # explicitly: a live secret must never be clobbered by a plain-keys-only
    # restore step (CLAUDE.md regel 6).
    assert status["tmdb_api_token"]["configured"] is True


async def test_restore_reapplies_password_policy(client):
    """Samme mønster som test_restore_reapplies_plain_settings_without_
    touching_secrets ovenfor, men for feature #174's egne typede felter."""
    await client.patch(
        "/api/settings/password-policy",
        json={"password_min_length": 16, "password_require_digit": True},
    )
    backup = (await client.get("/api/system/backup")).json()

    # Changed after the backup was taken — restore should bring back the
    # backed-up policy, exactly like plain settings above.
    await client.patch(
        "/api/settings/password-policy",
        json={"password_min_length": 8, "password_require_digit": False},
    )

    response = await client.post("/api/system/restore", json=backup)
    assert response.status_code == 200
    assert response.json()["password_policy_restored"] is True

    policy = (await client.get("/api/settings/password-policy")).json()
    assert policy["password_min_length"] == 16
    assert policy["password_require_digit"] is True


async def test_restore_ignores_the_pre_186_screening_policy_field_name_without_crashing(client):
    """Feature #186 renamed require_preferred_at_for_guests to
    require_preferred_at. A backup taken before the rename still has the old
    key inside its screening_request_policy dict — `SystemBackup.
    screening_request_policy` is a permissive `dict` (not the typed model),
    so it parses fine either way; the old key is then silently ignored by
    `ScreeningRequestPolicyUpdate` (Pydantic's default `extra="ignore"`),
    same graceful no-op as any other field missing from an older backup."""
    backup = (await client.get("/api/system/backup")).json()
    backup["screening_request_policy"] = {"require_preferred_at_for_guests": False}

    response = await client.post("/api/system/restore", json=backup)
    assert response.status_code == 200
    assert response.json()["screening_request_policy_restored"] is True

    policy = (await client.get("/api/settings/screening-request-policy")).json()
    assert policy["require_preferred_at"] is True


async def test_backup_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin3", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/system/backup")
        assert response.status_code == 403


async def test_restore_round_trip_preserves_everything(client, monkeypatch):
    fetch_calls = []

    async def fake_fetch(size, path):
        fetch_calls.append((size, path))
        return b"real-poster-bytes", "image/jpeg"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)

    await client.post("/api/movies", json={"title": "Roundtrip Movie", "tags": ["Favorite"], "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/tv-shows", json={"name": "Roundtrip Show", "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/reservations/hold", json={"seat_id": "N1-1", "scope": "global"})
    await client.get("/api/posters/w185/roundtrip.jpg")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as recipient_client:
        recipient = await recipient_client.post(
            "/api/auth/register", json={"username": "roundtriprecipient", "password": "testpassword123"}
        )
    await client.patch(f"/api/users/{recipient.json()['id']}/status", json={"status": "active"})
    await client.post("/api/messages", json={"subject": "Hej", "body": "Test", "recipient_user_id": None})
    backup = (await client.get("/api/system/backup")).json()

    # Mutate everything after the backup was taken.
    await client.post("/api/movies", json={"title": "Should Disappear After Restore", "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/reservations/hold", json={"seat_id": "N1-2", "scope": "global"})

    response = await client.post("/api/system/restore", json=backup)
    assert response.status_code == 200
    result = response.json()
    assert result["movies_imported"] == 1
    assert result["tv_shows_imported"] == 1
    assert result["users_imported"] == 2
    assert result["seat_reservations_imported"] == 1
    assert result["messages_imported"] == 1
    assert result["poster_cache_imported"] == 1
    assert result["password_policy_restored"] is True

    # Feature #153 — det er ikke nok at tallet stemmer; selve billed-bytes
    # skal også have overlevet base64-rundturen (mongo_json's "$binary") og
    # rent faktisk stå i databasen efter restore, ikke kun i backup-JSON'en.
    # Genfetch af samme sti skal derfor IKKE udløse et nyt TMDb-kald.
    fetch_calls.clear()
    poster_after_restore = await client.get("/api/posters/w185/roundtrip.jpg")
    assert poster_after_restore.status_code == 200
    assert poster_after_restore.content == b"real-poster-bytes"
    assert fetch_calls == []

    movies = (await client.get("/api/movies")).json()["items"]
    assert len(movies) == 1
    assert movies[0]["title"] == "Roundtrip Movie"
    assert movies[0]["tags"] == ["Favorite", "Tilføjet af testuser"]

    # BUGS.md #65 — the second hold (N1-2, taken after the backup) must be
    # gone, and the first (N1-1, in the backup) must still be there. Proves
    # seat_reservations actually round-trips through restore now, not just
    # that the restore call succeeds.
    reservations = (await client.get("/api/reservations?status=approved")).json()
    assert [r["seat_id"] for r in reservations] == ["N1-1"]

    # The logged-in session survives the restore because the same user
    # document (same _id) came back — proves the round trip didn't corrupt
    # user documents.
    me = await client.get("/api/users/me")
    assert me.status_code == 200


async def test_restore_requires_admin(client):
    backup = (await client.get("/api/system/backup")).json()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin4", "password": "testpassword123"}
        )
        response = await standard_client.post("/api/system/restore", json=backup)
        assert response.status_code == 403
