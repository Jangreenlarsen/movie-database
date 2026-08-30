"""Feature #199-opfølgning — valgfri e-mail ved registrering, samme mønster
som feature #140's fulde navn (test_full_name.py)."""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _fresh_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_register_stores_email(client):
    member = await _fresh_client()
    resp = await member.post(
        "/api/auth/register",
        json={"username": "emailguy", "password": "testpassword123", "email": "guy@example.com"},
    )
    assert resp.status_code in (200, 201)
    assert resp.json()["email"] == "guy@example.com"
    await member.aclose()


async def test_register_without_email_is_allowed_and_null(client):
    """Bevidst valgfri — samme "eksisterende API-kontrakt ikke brydes"-
    begrundelse som full_name."""
    member = await _fresh_client()
    resp = await member.post(
        "/api/auth/register", json={"username": "noemail", "password": "testpassword123"}
    )
    assert resp.status_code in (200, 201)
    assert resp.json()["email"] is None
    await member.aclose()


async def test_blank_email_is_normalized_to_null(client):
    member = await _fresh_client()
    resp = await member.post(
        "/api/auth/register",
        json={"username": "blankemail", "password": "testpassword123", "email": "   "},
    )
    assert resp.status_code in (200, 201)
    assert resp.json()["email"] is None
    await member.aclose()


async def test_register_rejects_a_malformed_email(client):
    member = await _fresh_client()
    resp = await member.post(
        "/api/auth/register",
        json={"username": "bademailuser", "password": "testpassword123", "email": "not-an-email"},
    )
    assert resp.status_code == 422
    await member.aclose()


async def test_registered_email_can_immediately_receive_notifications(client, monkeypatch):
    """Ende-til-ende-tjek af selve pointen med feltet: en bruger der satte
    sin e-mail ved oprettelse skal med det samme kunne modtage en
    notifikation, uden først at skulle sætte den igen via
    PATCH /users/{id}/email (feature #197's message_service._send_emails)."""
    from app.core.config import settings
    from app.integrations import email_client

    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")

    member = await _fresh_client()
    created = await member.post(
        "/api/auth/register",
        json={"username": "notifyme", "password": "testpassword123", "email": "notifyme@example.com"},
    )
    await client.patch(f"/api/users/{created.json()['id']}/status", json={"status": "active"})
    await member.aclose()

    sent = []

    async def fake_send_email(to, subject, text, html=None):
        sent.append(to)
        return True

    monkeypatch.setattr(email_client, "send_email", fake_send_email)

    response = await client.post(
        "/api/messages",
        json={"subject": "Velkommen", "body": "Tekst", "recipient_user_id": created.json()["id"]},
    )
    assert response.status_code == 201
    assert sent == ["notifyme@example.com"]
