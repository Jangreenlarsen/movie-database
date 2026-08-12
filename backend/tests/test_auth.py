async def test_register_creates_user_and_logs_in(raw_client):
    response = await raw_client.post(
        "/api/auth/register", json={"username": "alice", "password": "supersecret1"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert "access_token" in raw_client.cookies

    me = await raw_client.get("/api/users/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


async def test_register_rejects_duplicate_username(raw_client):
    await raw_client.post(
        "/api/auth/register", json={"username": "bob", "password": "supersecret1"}
    )
    duplicate = await raw_client.post(
        "/api/auth/register", json={"username": "bob", "password": "anotherpass1"}
    )
    assert duplicate.status_code == 409


async def test_register_rejects_short_password(raw_client):
    response = await raw_client.post(
        "/api/auth/register", json={"username": "carol", "password": "short"}
    )
    assert response.status_code == 422


async def test_login_with_correct_credentials(raw_client):
    await raw_client.post(
        "/api/auth/register", json={"username": "dave", "password": "correcthorse1"}
    )
    await raw_client.post("/api/auth/logout")

    response = await raw_client.post(
        "/api/auth/login", json={"username": "dave", "password": "correcthorse1"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "dave"


async def test_login_with_wrong_password_returns_401(raw_client):
    await raw_client.post(
        "/api/auth/register", json={"username": "erin", "password": "correcthorse1"}
    )
    response = await raw_client.post(
        "/api/auth/login", json={"username": "erin", "password": "wrongpassword"}
    )
    assert response.status_code == 401


async def test_login_is_case_insensitive_on_username(raw_client):
    """Regression test for BUGS.md #21 — iOS Safari auto-capitalizes the
    first letter of a plain text input by default, silently turning
    "jgl" into "Jgl" as the user types. Login must not treat that as a
    different account."""
    await raw_client.post(
        "/api/auth/register", json={"username": "jgl", "password": "correcthorse1"}
    )
    await raw_client.post("/api/auth/logout")

    response = await raw_client.post(
        "/api/auth/login", json={"username": "Jgl", "password": "correcthorse1"}
    )
    assert response.status_code == 200
    # The originally-registered casing is preserved for display, not
    # silently replaced by whatever casing was used to log in.
    assert response.json()["username"] == "jgl"


async def test_register_rejects_case_variant_of_existing_username(raw_client):
    await raw_client.post(
        "/api/auth/register", json={"username": "frank", "password": "correcthorse1"}
    )
    duplicate = await raw_client.post(
        "/api/auth/register", json={"username": "FRANK", "password": "anotherpass1"}
    )
    assert duplicate.status_code == 409


async def test_migrates_users_missing_username_normalized(db):
    """Regression test for BUGS.md #21 — a user document created before
    this field existed (e.g. Jan's real production account) must still be
    able to log in with any casing after the migration runs."""
    from datetime import datetime, timezone

    from app.repositories import user_repository

    now = datetime.now(timezone.utc)
    await db[user_repository.COLLECTION].insert_one(
        {
            "username": "grace",
            "password_hash": "irrelevant-for-this-test",
            "role": "standard",
            "settings": user_repository.DEFAULT_SETTINGS,
            "created_at": now,
        }
    )

    await user_repository._migrate_username_normalized(db)

    migrated = await db[user_repository.COLLECTION].find_one({"username": "grace"})
    assert migrated["username_normalized"] == "grace"


async def test_me_requires_authentication(raw_client):
    response = await raw_client.get("/api/users/me")
    assert response.status_code == 401


async def test_movies_endpoint_requires_authentication(raw_client):
    response = await raw_client.get("/api/movies")
    assert response.status_code == 401


async def test_logout_clears_session(client):
    me_before = await client.get("/api/users/me")
    assert me_before.status_code == 200

    await client.post("/api/auth/logout")

    me_after = await client.get("/api/users/me")
    assert me_after.status_code == 401


async def test_update_and_read_settings(client):
    response = await client.patch(
        "/api/users/me/settings",
        json={
            "sort_field": "rating",
            "sort_direction": "asc",
            "visible_fields": {
                "year": False,
                "tags": True,
                "format": True,
                "audio_types": False,
                "rating": True,
                "genres": True,
            },
        },
    )
    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["sort_field"] == "rating"
    assert settings["sort_direction"] == "asc"
    assert settings["visible_fields"]["format"] is True
    # Feature #113 — regression guard for BUGS.md #22's failure mode: a
    # VisibleFields field missing from the Pydantic model makes PATCH
    # silently drop it instead of persisting it.
    assert settings["visible_fields"]["genres"] is True

    me = await client.get("/api/users/me")
    assert me.json()["settings"]["sort_field"] == "rating"


async def test_new_user_has_default_settings(client):
    me = await client.get("/api/users/me")
    settings = me.json()["settings"]
    assert settings["sort_field"] is None
    assert settings["visible_fields"]["year"] is True
    assert settings["visible_fields"]["rating"] is False
    assert settings["sort_levels"] == []
    assert settings["sort_presets"] == []
    assert settings["card_size"] == "medium"
    # Feature #89 — dansk er kildesproget og dermed standarden.
    assert settings["language"] == "da"
    # Feature #88 — Plex-badget er fra som standard.
    assert settings["visible_fields"]["plex"] is False
    # Feature #113 — genre-badget er ligeledes fra som standard.
    assert settings["visible_fields"]["genres"] is False
    # Feature #110 — usat betyder "følg systemets prefers-color-scheme",
    # ikke en fast standardværdi (se Theme's docstring i models/user.py).
    assert settings["theme"] is None


async def test_language_roundtrip_and_rejects_unknown_language(client):
    """Feature #89 — sproget gemmes pr. bruger (Jans valg 2026-08-08), så det
    følger med på tværs af enheder frem for at ligge i én browsers storage."""
    response = await client.patch("/api/users/me/settings", json={"language": "en"})
    assert response.status_code == 200
    assert response.json()["settings"]["language"] == "en"

    me = await client.get("/api/users/me")
    assert me.json()["settings"]["language"] == "en"

    # Et ukendt sprog må afvises i backend, ikke bare falde tilbage stiltiende
    # — ellers ville en tastefejl gemme en værdi ingen frontend kan bruge.
    invalid = await client.patch("/api/users/me/settings", json={"language": "de"})
    assert invalid.status_code == 422


async def test_card_size_roundtrip_and_rejects_invalid_value(client):
    """Feature #59 — one shared card-size preference across Film and
    TV-serier (Jans bekræftede valg 2026-08-02)."""
    response = await client.patch("/api/users/me/settings", json={"card_size": "large"})
    assert response.status_code == 200
    assert response.json()["settings"]["card_size"] == "large"

    me = await client.get("/api/users/me")
    assert me.json()["settings"]["card_size"] == "large"

    invalid = await client.patch("/api/users/me/settings", json={"card_size": "huge"})
    assert invalid.status_code == 422


async def test_theme_roundtrip_and_rejects_invalid_value(client):
    """Feature #110 — personligt tema-valg (Jans ønske 2026-08-10)."""
    response = await client.patch("/api/users/me/settings", json={"theme": "dark"})
    assert response.status_code == 200
    assert response.json()["settings"]["theme"] == "dark"

    me = await client.get("/api/users/me")
    assert me.json()["settings"]["theme"] == "dark"

    # Nulstilling til systemets egen præference (usat) skal stadig kunne
    # sættes eksplicit tilbage til null.
    reset = await client.patch("/api/users/me/settings", json={"theme": None})
    assert reset.status_code == 200
    assert reset.json()["settings"]["theme"] is None

    invalid = await client.patch("/api/users/me/settings", json={"theme": "sepia"})
    assert invalid.status_code == 422


async def test_multi_level_sort_and_presets_roundtrip(client):
    """Regression test for FEATURES.md #17/#27."""
    levels = [
        {"field": "format", "direction": "asc"},
        {"field": "title", "direction": "desc"},
    ]
    response = await client.patch("/api/users/me/settings", json={"sort_levels": levels})
    assert response.status_code == 200
    assert response.json()["settings"]["sort_levels"] == levels

    presets = [{"name": "Efter format", "levels": levels}]
    response = await client.patch("/api/users/me/settings", json={"sort_presets": presets})
    assert response.status_code == 200
    # A preset sent without the feature #44 filter fields round-trips with
    # them filled in as defaults (empty/None) — not absent.
    assert response.json()["settings"]["sort_presets"] == [
        {
            "name": "Efter format",
            "levels": levels,
            "query": None,
            "tags": [],
            "formats": [],
            "audio_types": [],
            "media_types": [],
            "watched": None,
        }
    ]

    # sort_levels must survive a later update that only touches sort_presets.
    me = await client.get("/api/users/me")
    assert me.json()["settings"]["sort_levels"] == levels


async def test_settings_updates_do_not_clobber_unrelated_keys(client):
    """Regression test: Library.jsx fires several `PATCH .../settings` calls
    in quick succession with no client-side queuing (e.g. adjusting sort
    levels, then immediately saving a preset). The old implementation read
    the whole `settings` sub-document, merged in one field, and overwrote it
    wholesale — two such requests racing could silently lose whichever
    write landed first. `auth_service.update_settings` now applies only the
    given field via a dotted-path `$set`, so unrelated keys set by earlier
    or later requests are never touched, regardless of ordering."""
    await client.patch(
        "/api/users/me/settings",
        json={"visible_fields": {"year": True, "tags": True, "format": True, "audio_types": False, "rating": False}},
    )
    await client.patch("/api/users/me/settings", json={"sort_levels": [{"field": "title", "direction": "asc"}]})
    response = await client.patch(
        "/api/users/me/settings",
        json={"sort_presets": [{"name": "By title", "levels": [{"field": "title", "direction": "asc"}]}]},
    )

    settings = response.json()["settings"]
    assert settings["visible_fields"]["format"] is True
    assert settings["sort_levels"] == [{"field": "title", "direction": "asc"}]
    assert settings["sort_presets"] == [
        {
            "name": "By title",
            "levels": [{"field": "title", "direction": "asc"}],
            "query": None,
            "tags": [],
            "formats": [],
            "audio_types": [],
            "media_types": [],
            "watched": None,
        }
    ]


async def test_preset_can_capture_full_filter_state(client):
    """Regression test for FEATURES.md #44 — a saved "view" is more than
    just sort order."""
    preset = {
        "name": "Ikke sete actionfilm",
        "levels": [{"field": "title", "direction": "asc"}],
        "query": "matrix",
        "tags": ["favorit"],
        "formats": ["F-BD"],
        "audio_types": ["Atmos"],
        "media_types": ["Fysisk"],
        "watched": False,
    }
    response = await client.patch("/api/users/me/settings", json={"sort_presets": [preset]})
    assert response.status_code == 200
    assert response.json()["settings"]["sort_presets"] == [preset]


async def test_preset_without_filter_fields_defaults_gracefully(client):
    """A preset saved before feature #44 (sort-only) must still validate."""
    old_style_preset = {"name": "Gammel preset", "levels": [{"field": "year", "direction": "desc"}]}
    response = await client.patch(
        "/api/users/me/settings", json={"sort_presets": [old_style_preset]}
    )
    assert response.status_code == 200
    saved = response.json()["settings"]["sort_presets"][0]
    assert saved["name"] == "Gammel preset"
    assert saved["query"] is None
    assert saved["tags"] == []
    assert saved["watched"] is None


async def test_email_as_username_is_rejected_with_a_usable_message(raw_client):
    """BUGS.md #54 — reglen er bevaret (Jans valg 2026-08-09), men beskeden
    skal fortælle hvad der er galt. Frontendens `readableDetail` trækker
    `msg` ud af FastAPIs 422-liste; før blev hele listen givet til
    `new Error(...)` og brugeren så "[object Object]"."""
    response = await raw_client.post(
        "/api/auth/register", json={"username": "jan@example.com", "password": "testpassword123"}
    )
    assert response.status_code == 422
    messages = [item["msg"] for item in response.json()["detail"]]
    assert any("e-mailadresse" in message for message in messages), messages
    assert any("bogstaver, tal" in message for message in messages), messages
