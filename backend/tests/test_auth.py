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
            },
        },
    )
    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["sort_field"] == "rating"
    assert settings["sort_direction"] == "asc"
    assert settings["visible_fields"]["format"] is True

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
    assert response.json()["settings"]["sort_presets"] == presets

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
    assert settings["sort_presets"] == [{"name": "By title", "levels": [{"field": "title", "direction": "asc"}]}]
