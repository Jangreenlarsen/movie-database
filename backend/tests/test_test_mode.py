"""Feature #217 (Jan: "vi skal have en funktion for adm i settings hvor vi
kan sætte at 'test' tilstand som primæret vil betyde at email og beskeder
ikke sendes ud af system i test mode", uddybet: begge kanaler skal stoppes
helt — hverken e-mail eller in-app besked oprettes overhovedet mens
test-tilstand er aktiv)."""

from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.integrations import email_client
from app.main import app


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


async def test_patch_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmintestmode", "password": "testpassword123"}
        )
        response = await standard_client.patch("/api/settings/test-mode", json={"test_mode": True})
        assert response.status_code == 403


async def test_get_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmintestmode2", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/settings/test-mode")
        assert response.status_code == 403


async def test_default_is_off(client):
    response = await client.get("/api/settings/test-mode")
    assert response.status_code == 200
    assert response.json() == {"test_mode": False}


async def test_updating_the_policy_takes_effect_immediately(client):
    response = await client.patch("/api/settings/test-mode", json={"test_mode": True})
    assert response.status_code == 200
    assert response.json()["test_mode"] is True
    assert settings.test_mode is True


async def test_policy_change_is_audit_logged(client):
    await client.patch("/api/settings/test-mode", json={"test_mode": True})

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    matching = [e for e in entries if e["action"] == "test_mode_policy.updated"]
    assert len(matching) == 1
    assert "test_mode=True" in matching[0]["detail"]


async def test_manual_message_send_is_rejected_with_a_clear_error_while_test_mode_is_active(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "test_mode", True)

    response = await client.post(
        "/api/messages", json={"subject": "Hej", "body": "Test besked"}
    )
    assert response.status_code == 409
    assert "test-tilstand" in response.json()["detail"]


async def test_no_in_app_message_or_email_is_created_by_a_poll_notification_while_test_mode_is_active(
    client, monkeypatch
):
    """Bekræfter at feature #216's notify_poll_cancelled (og dermed enhver
    notify_*-funktion, da de alle går gennem samme send()) bliver et rent,
    tavst no-op — hverken indbakke-besked eller e-mail."""
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)

    a = (
        await client.post(
            "/api/movies", json={"title": "Test-tilstand A", "media_type": "Fysisk", "format": "F-DVD"}
        )
    ).json()["id"]
    b = (
        await client.post(
            "/api/movies", json={"title": "Test-tilstand B", "media_type": "Fysisk", "format": "F-DVD"}
        )
    ).json()["id"]

    voter_transport = ASGITransport(app=app)
    voter = AsyncClient(transport=voter_transport, base_url="http://test")
    register = await voter.post(
        "/api/auth/register", json={"username": "testmode_voter", "password": "testpassword123"}
    )
    await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})

    poll = (
        await client.post(
            "/api/polls",
            json={"candidates": [{"media_kind": "movie", "movie_id": a}, {"media_kind": "movie", "movie_id": b}]},
        )
    ).json()
    await voter.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})

    monkeypatch.setattr(settings, "test_mode", True)
    response = await client.delete(f"/api/polls/{poll['id']}")
    assert response.status_code == 204

    inbox = (await voter.get("/api/messages/inbox")).json()
    assert inbox == []
    assert len(calls) == 0
    await voter.aclose()
