"""Besked-systemet (feature #100).

En admin kan sende en besked til alle eller til én bruger. Modtageren ser
den som en banner indtil den lukkes, og afsenderen kan se hvem der har
læst den.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.errors import EmailRateLimitedError
from app.integrations import email_client
from app.main import app


@pytest_asyncio.fixture
async def second_user(client, raw_client):
    """En ekstra, aktiv bruger med sin egen session. `client`-fixturen er
    den første registrerede og dermed admin (feature #66's bootstrap)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        register = await other.post(
            "/api/auth/register", json={"username": "modtager", "password": "testpassword123"}
        )
        user_id = register.json()["id"]
        await client.patch(f"/api/users/{user_id}/status", json={"status": "active"})
        yield {"id": user_id, "client": other}


# --- afsendelse -------------------------------------------------------------


async def test_broadcast_reaches_every_active_user(client, second_user):
    response = await client.post(
        "/api/messages", json={"subject": "Visning fredag", "body": "Kom kl. 19."}
    )
    assert response.status_code == 201
    message = response.json()
    assert message["is_broadcast"] is True
    assert [r["username"] for r in message["recipients"]] == ["modtager"]

    inbox = (await second_user["client"].get("/api/messages/inbox")).json()
    assert [m["subject"] for m in inbox] == ["Visning fredag"]


async def test_sender_does_not_receive_their_own_broadcast(client, second_user):
    """Man skal ikke mødes af en banner om sin egen besked."""
    await client.post("/api/messages", json={"subject": "Hej alle", "body": "Tekst"})

    own_inbox = (await client.get("/api/messages/inbox")).json()
    assert own_inbox == []


async def test_personal_message_goes_to_only_that_user(client, second_user, raw_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as third:
        register = await third.post(
            "/api/auth/register", json={"username": "udenfor", "password": "testpassword123"}
        )
        await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})

        response = await client.post(
            "/api/messages",
            json={
                "subject": "Kun til dig",
                "body": "Tekst",
                "recipient_user_id": second_user["id"],
            },
        )
        assert response.json()["is_broadcast"] is False
        assert response.json()["recipient_count"] == 1

        assert len((await second_user["client"].get("/api/messages/inbox")).json()) == 1
        assert (await third.get("/api/messages/inbox")).json() == []


async def test_broadcast_skips_users_who_are_not_active(client, raw_client):
    """En `pending` bruger kan ikke bruge appen og ville bare stå som ulæst
    for evigt."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as pending:
        await pending.post(
            "/api/auth/register", json={"username": "afventer", "password": "testpassword123"}
        )

    response = await client.post("/api/messages", json={"subject": "Emne", "body": "Tekst"})
    assert response.status_code == 409
    assert "ingen aktive brugere" in response.text


async def test_personal_message_to_unknown_user_is_rejected(client, second_user):
    response = await client.post(
        "/api/messages",
        json={"subject": "Emne", "body": "Tekst", "recipient_user_id": "000000000000000000000000"},
    )
    assert response.status_code == 404


async def test_subject_and_body_are_required(client, second_user):
    for payload in ({"subject": "", "body": "Tekst"}, {"subject": "Emne", "body": "   "}):
        response = await client.post("/api/messages", json=payload)
        assert response.status_code in (409, 422), payload


# --- modtagerens side -------------------------------------------------------


async def test_closing_the_banner_marks_it_read(client, second_user):
    await client.post("/api/messages", json={"subject": "Emne", "body": "Tekst"})
    inbox = (await second_user["client"].get("/api/messages/inbox")).json()
    message_id = inbox[0]["id"]

    marked = await second_user["client"].post(f"/api/messages/{message_id}/read")
    assert marked.status_code == 204

    assert (await second_user["client"].get("/api/messages/inbox")).json() == []


async def test_reading_is_per_user_not_global(client, second_user):
    """En rundsendt besked må ikke forsvinde for alle andre, fordi én
    modtager lukkede den."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as third:
        register = await third.post(
            "/api/auth/register", json={"username": "trediemand", "password": "testpassword123"}
        )
        await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})

        await client.post("/api/messages", json={"subject": "Til alle", "body": "Tekst"})
        message_id = (await second_user["client"].get("/api/messages/inbox")).json()[0]["id"]
        await second_user["client"].post(f"/api/messages/{message_id}/read")

        assert (await second_user["client"].get("/api/messages/inbox")).json() == []
        assert len((await third.get("/api/messages/inbox")).json()) == 1


async def test_marking_a_message_you_did_not_receive_is_a_404(client, second_user):
    """Samme svar som en besked der ikke findes — hvilke beskeder der findes
    til andre, er ikke ens egen oplysning."""
    sent = await client.post(
        "/api/messages",
        json={"subject": "Kun til dig", "body": "Tekst", "recipient_user_id": second_user["id"]},
    )
    # Afsenderen er ikke selv modtager af den personlige besked.
    response = await client.post(f"/api/messages/{sent.json()['id']}/read")
    assert response.status_code == 404


# --- afsenderens oversigt ---------------------------------------------------


async def test_sender_sees_read_status(client, second_user):
    sent = await client.post("/api/messages", json={"subject": "Emne", "body": "Tekst"})
    message_id = sent.json()["id"]

    listed = (await client.get("/api/messages")).json()
    assert listed[0]["read_count"] == 0
    assert listed[0]["recipient_count"] == 1

    inbox_id = (await second_user["client"].get("/api/messages/inbox")).json()[0]["id"]
    await second_user["client"].post(f"/api/messages/{inbox_id}/read")

    listed = (await client.get("/api/messages")).json()
    assert listed[0]["read_count"] == 1
    assert listed[0]["recipients"][0]["read_at"] is not None
    assert message_id == listed[0]["id"]


async def test_only_admins_may_send_or_list(client, second_user):
    forbidden_post = await second_user["client"].post(
        "/api/messages", json={"subject": "Emne", "body": "Tekst"}
    )
    forbidden_list = await second_user["client"].get("/api/messages")
    assert forbidden_post.status_code == 403
    assert forbidden_list.status_code == 403


async def test_deleting_a_message_removes_it_for_recipients(client, second_user):
    sent = await client.post("/api/messages", json={"subject": "Fortrudt", "body": "Tekst"})

    deleted = await client.delete(f"/api/messages/{sent.json()['id']}")
    assert deleted.status_code == 204
    assert (await second_user["client"].get("/api/messages/inbox")).json() == []
    assert (await client.get("/api/messages")).json() == []


async def test_deleting_an_unknown_message_is_a_404(client):
    response = await client.delete("/api/messages/000000000000000000000000")
    assert response.status_code == 404


async def test_inbox_requires_login(raw_client):
    response = await raw_client.get("/api/messages/inbox")
    assert response.status_code == 401


# --- e-mail-notifikationer (feature #197) ------------------------------------


async def test_send_emails_a_recipient_with_an_email_set_when_resend_is_configured(
    client, second_user, monkeypatch
):
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")
    await client.patch(f"/api/users/{second_user['id']}/email", json={"email": "modtager@example.com"})

    sent = []

    async def fake_send_email(to, subject, text, html=None):
        sent.append((to, subject, text))
        return True

    monkeypatch.setattr(email_client, "send_email", fake_send_email)

    response = await client.post("/api/messages", json={"subject": "Emne", "body": "Krop"})
    assert response.status_code == 201
    assert sent == [("modtager@example.com", "Emne", "Krop")]


async def test_send_does_not_attempt_email_when_resend_is_not_configured(client, second_user, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "email_from_address", "")
    await client.patch(f"/api/users/{second_user['id']}/email", json={"email": "modtager@example.com"})

    async def fake_send_email(to, subject, text, html=None):
        raise AssertionError("should not be called when Resend is unconfigured")

    monkeypatch.setattr(email_client, "send_email", fake_send_email)

    response = await client.post("/api/messages", json={"subject": "Emne", "body": "Krop"})
    assert response.status_code == 201


async def test_send_skips_a_recipient_without_an_email(client, second_user, monkeypatch):
    """Ny bruger har ingen e-mail sat (feltet er valgfrit) — no-op for netop
    den modtager, ikke en fejl."""
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")

    async def fake_send_email(to, subject, text, html=None):
        raise AssertionError("should not be called for a recipient with no email set")

    monkeypatch.setattr(email_client, "send_email", fake_send_email)

    response = await client.post("/api/messages", json={"subject": "Emne", "body": "Krop"})
    assert response.status_code == 201


async def test_send_creates_the_in_app_message_even_if_email_sending_fails(
    client, second_user, monkeypatch
):
    """En mail-fejl må aldrig vælte selve besked-oprettelsen (CLAUDE.md
    regel 16 — best-effort sidekanal)."""
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")
    await client.patch(f"/api/users/{second_user['id']}/email", json={"email": "modtager@example.com"})

    async def fake_send_email(to, subject, text, html=None):
        raise RuntimeError("Resend er nede")

    monkeypatch.setattr(email_client, "send_email", fake_send_email)

    response = await client.post("/api/messages", json={"subject": "Emne", "body": "Krop"})
    assert response.status_code == 201
    inbox = (await second_user["client"].get("/api/messages/inbox")).json()
    assert [m["subject"] for m in inbox] == ["Emne"]


async def test_send_stops_the_rest_of_the_batch_on_a_rate_limit(client, second_user, raw_client, monkeypatch):
    """En 429 fra Resend skal stoppe resten af udsendelsen med det samme
    (regel 16 — bulk-kald mod en ekstern API), ikke blive ved med at ramme
    en allerede rate-limitet tjeneste for hver resterende modtager."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as third:
        register = await third.post(
            "/api/auth/register", json={"username": "tredjemodtager", "password": "testpassword123"}
        )
        third_id = register.json()["id"]
    await client.patch(f"/api/users/{third_id}/status", json={"status": "active"})
    await client.patch(f"/api/users/{third_id}/email", json={"email": "tredje@example.com"})

    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")
    # `second_user` has no email set (skipped, doesn't count toward the
    # send attempts below) — only the third recipient does.
    await client.patch(f"/api/users/{second_user['id']}/email", json={"email": "modtager@example.com"})

    calls = []

    async def fake_send_email(to, subject, text, html=None):
        calls.append(to)
        raise EmailRateLimitedError()

    monkeypatch.setattr(email_client, "send_email", fake_send_email)

    response = await client.post("/api/messages", json={"subject": "Emne", "body": "Krop"})
    assert response.status_code == 201
    # Kun ÉT forsøg — udsendelsen stoppede efter den første 429 i stedet for
    # at forsøge den anden modtager også.
    assert len(calls) == 1
