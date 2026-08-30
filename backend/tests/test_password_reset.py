"""Feature #205 (Jan: "1" af "1 og 2 og så lad os se på #162" — selvbetjent
"glemt adgangskode" via e-mail, muliggjort af feature #197's Resend-
infrastruktur). Dækker: anti-enumerering (samme svar uanset om e-mailen
findes), token-generering/hash/udløb/engangsbrug, Origin-validering af
nulstillings-linkets domæne mod cors_origin_list, og at #171's admin-
assisterede vej stadig virker uændret ved siden af."""

import hashlib
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.integrations import email_client
from app.services import auth_service


def _configure_resend(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")


def _capture_email(monkeypatch):
    calls = []

    async def fake_send_email(to, subject, text, html=None):
        calls.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    monkeypatch.setattr(email_client, "send_email", fake_send_email)
    return calls


async def _register_with_email(client, username, email, password="testpassword123"):
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    other = AsyncClient(transport=transport, base_url="http://test")
    register = await other.post(
        "/api/auth/register", json={"username": username, "password": password, "email": email}
    )
    await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})
    await other.aclose()
    return register.json()


async def test_forgot_password_sends_a_reset_link_for_a_registered_email(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    await _register_with_email(client, "resetuser1", "resetuser1@example.com")

    response = await client.post(
        "/api/auth/forgot-password", json={"email": "resetuser1@example.com"}
    )
    assert response.status_code == 200

    assert len(calls) == 1
    assert calls[0]["to"] == "resetuser1@example.com"
    assert "token=" in calls[0]["text"]
    assert "token=" in calls[0]["html"]


async def test_forgot_password_email_lookup_is_case_insensitive(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    await _register_with_email(client, "resetuser2", "ResetUser2@Example.com")

    response = await client.post(
        "/api/auth/forgot-password", json={"email": "resetuser2@example.com"}
    )
    assert response.status_code == 200
    assert len(calls) == 1


async def test_forgot_password_gives_the_same_response_for_an_unknown_email(client, monkeypatch):
    """Anti-enumerering — svaret må ikke afsløre om adressen findes."""
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)

    known = await client.post(
        "/api/auth/forgot-password", json={"email": "does-not-exist@example.com"}
    )
    assert known.status_code == 200
    assert known.json()["message"]
    assert len(calls) == 0


async def test_forgot_password_returns_the_same_message_for_known_and_unknown_email(
    client, monkeypatch
):
    _configure_resend(monkeypatch)
    _capture_email(monkeypatch)
    await _register_with_email(client, "resetuser3", "resetuser3@example.com")

    known = await client.post(
        "/api/auth/forgot-password", json={"email": "resetuser3@example.com"}
    )
    unknown = await client.post(
        "/api/auth/forgot-password", json={"email": "nobody-here@example.com"}
    )
    assert known.json()["message"] == unknown.json()["message"]


async def test_forgot_password_is_a_noop_for_an_account_with_no_email(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    # `client`'s bootstrap admin has no email set.
    response = await client.post("/api/auth/forgot-password", json={"email": "nope@example.com"})
    assert response.status_code == 200
    assert len(calls) == 0


async def test_forgot_password_is_a_noop_for_a_pending_account(client, monkeypatch):
    """En endnu-ikke-godkendt konto kan ikke logge ind overhovedet — skal
    heller ikke kunne bruges til at udløse et reset-link."""
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    other = AsyncClient(transport=transport, base_url="http://test")
    await other.post(
        "/api/auth/register",
        json={"username": "pendinguser", "password": "testpassword123", "email": "pending@example.com"},
    )
    await other.aclose()

    response = await client.post("/api/auth/forgot-password", json={"email": "pending@example.com"})
    assert response.status_code == 200
    assert len(calls) == 0


async def test_forgot_password_fails_clearly_when_resend_is_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "email_from_address", "")

    response = await client.post("/api/auth/forgot-password", json={"email": "whoever@example.com"})
    assert response.status_code == 503
    assert "ikke konfigureret" in response.json()["detail"]


async def test_reset_link_uses_the_requesting_origin_when_it_is_an_allowed_cors_origin(
    client, monkeypatch
):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    monkeypatch.setattr(
        settings, "cors_origins", "http://localhost:5173,https://movie.laces.dk"
    )
    await _register_with_email(client, "resetuser4", "resetuser4@example.com")

    response = await client.post(
        "/api/auth/forgot-password",
        json={"email": "resetuser4@example.com"},
        headers={"Origin": "https://movie.laces.dk"},
    )
    assert response.status_code == 200
    assert "https://movie.laces.dk/reset-password?token=" in calls[0]["text"]


async def test_reset_link_ignores_an_origin_that_is_not_in_the_cors_allowlist(client, monkeypatch):
    """Sikkerheds-kritisk: en angriber der selv sætter en vilkårlig
    Origin-header må IKKE kunne styre hvilket domæne der ender i offerets
    mail (ville muliggøre token-tyveri via en falsk 'nulstil'-side)."""
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    monkeypatch.setattr(settings, "cors_origins", "http://localhost:5173")
    await _register_with_email(client, "resetuser5", "resetuser5@example.com")

    response = await client.post(
        "/api/auth/forgot-password",
        json={"email": "resetuser5@example.com"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 200
    assert "evil.example" not in calls[0]["text"]
    assert "http://localhost:5173/reset-password?token=" in calls[0]["text"]


async def test_reset_password_with_a_valid_token_actually_changes_the_password(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    await _register_with_email(client, "resetuser6", "resetuser6@example.com", password="oldpassword123")

    await client.post("/api/auth/forgot-password", json={"email": "resetuser6@example.com"})
    token = calls[0]["text"].split("token=")[1].split()[0].split("\n")[0]

    reset = await client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": "brandnewpassword123"}
    )
    assert reset.status_code == 204

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    fresh = AsyncClient(transport=transport, base_url="http://test")
    old_login = await fresh.post(
        "/api/auth/login", json={"username": "resetuser6", "password": "oldpassword123"}
    )
    assert old_login.status_code == 401
    new_login = await fresh.post(
        "/api/auth/login", json={"username": "resetuser6", "password": "brandnewpassword123"}
    )
    assert new_login.status_code == 200
    await fresh.aclose()


async def test_reset_password_token_can_only_be_used_once(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    await _register_with_email(client, "resetuser7", "resetuser7@example.com")

    await client.post("/api/auth/forgot-password", json={"email": "resetuser7@example.com"})
    token = calls[0]["text"].split("token=")[1].split()[0].split("\n")[0]

    first = await client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": "firstnewpassword123"}
    )
    assert first.status_code == 204

    second = await client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": "secondnewpassword123"}
    )
    assert second.status_code == 400
    assert "ugyldigt" in second.json()["detail"].lower()


async def test_reset_password_rejects_an_unknown_token(client):
    response = await client.post(
        "/api/auth/reset-password", json={"token": "not-a-real-token", "new_password": "somepassword123"}
    )
    assert response.status_code == 400


async def test_reset_password_rejects_an_expired_token(client, monkeypatch, db):
    """Simulerer et udløbet token direkte i databasen — hurtigere og mere
    robust end at vente et rigtigt klokketime i testen."""
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    await _register_with_email(client, "resetuser8", "resetuser8@example.com")

    await client.post("/api/auth/forgot-password", json={"email": "resetuser8@example.com"})
    token = calls[0]["text"].split("token=")[1].split()[0].split("\n")[0]
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    await db["users"].update_one(
        {"reset_token_hash": token_hash},
        {"$set": {"reset_token_expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}},
    )

    response = await client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": "somepassword123"}
    )
    assert response.status_code == 400


async def test_reset_password_rejects_a_password_that_fails_policy(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    await _register_with_email(client, "resetuser9", "resetuser9@example.com")

    await client.post("/api/auth/forgot-password", json={"email": "resetuser9@example.com"})
    token = calls[0]["text"].split("token=")[1].split()[0].split("\n")[0]

    response = await client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": "short"}
    )
    assert response.status_code == 422


async def test_admin_assisted_reset_still_works_unchanged(client, monkeypatch):
    """Feature #171 forbliver den eneste vej for en konto uden e-mail —
    denne feature (#205) må ikke have rørt den."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    other = AsyncClient(transport=transport, base_url="http://test")
    register = await other.post(
        "/api/auth/register", json={"username": "noemailuser", "password": "testpassword123"}
    )
    await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})
    await other.aclose()

    response = await client.post(f"/api/users/{register.json()['id']}/reset-password")
    assert response.status_code == 200
    assert response.json()["username"] == "noemailuser"
