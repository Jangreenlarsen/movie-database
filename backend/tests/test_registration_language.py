"""Sprogvalget i login-boksen (feature #97).

Sproget gemmes normalt pr. bruger i databasen, men på login-skærmen findes
der ingen bruger endnu. Valget dér følger med registreringen, så en ny konto
starter på det sprog brugeren allerede har valgt.
"""


async def test_registration_without_language_defaults_to_source_language(raw_client):
    """Dansk er kildesproget — en klient der ikke sender feltet må ikke
    fejle, den skal bare få standarden."""
    response = await raw_client.post(
        "/api/auth/register", json={"username": "udenvalg", "password": "testpassword123"}
    )
    assert response.status_code == 201
    assert response.json()["settings"]["language"] == "da"


async def test_registration_language_becomes_the_account_language(raw_client):
    response = await raw_client.post(
        "/api/auth/register",
        json={"username": "englishuser", "password": "testpassword123", "language": "en"},
    )
    assert response.status_code == 201
    assert response.json()["settings"]["language"] == "en"

    me = await raw_client.get("/api/users/me")
    assert me.json()["settings"]["language"] == "en"


async def test_registration_rejects_an_unknown_language(raw_client):
    response = await raw_client.post(
        "/api/auth/register",
        json={"username": "tysker", "password": "testpassword123", "language": "de"},
    )
    assert response.status_code == 422


async def test_registration_language_does_not_leak_into_later_registrations(raw_client, db):
    """DEFAULT_SETTINGS er et modul-globalt dict. Blev sprogvalget skrevet
    ind i det frem for i en kopi, ville den næste bruger arve det."""
    await raw_client.post(
        "/api/auth/register",
        json={"username": "foersteuser", "password": "testpassword123", "language": "en"},
    )
    await raw_client.post("/api/auth/logout")

    second = await raw_client.post(
        "/api/auth/register", json={"username": "andenuser", "password": "testpassword123"}
    )
    assert second.json()["settings"]["language"] == "da"


async def test_registration_language_does_not_disturb_other_default_settings(raw_client):
    response = await raw_client.post(
        "/api/auth/register",
        json={"username": "komplet", "password": "testpassword123", "language": "en"},
    )
    settings = response.json()["settings"]
    assert settings["card_size"] == "medium"
    assert settings["page_size"] == 50
    assert settings["visible_fields"]["year"] is True
