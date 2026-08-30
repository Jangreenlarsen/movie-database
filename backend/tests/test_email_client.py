import httpx
import pytest

from app.core.config import settings
from app.core.errors import EmailRateLimitedError
from app.integrations import email_client


@pytest.fixture(autouse=True)
def _reset_email_settings(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")


async def test_send_email_returns_true_on_success(monkeypatch):
    async def fake_post(self, url, headers=None, json=None):
        assert url == "https://api.resend.com/emails"
        assert headers == {"Authorization": "Bearer test-key"}
        assert json == {
            "from": "Voldby BIO <noreply@laces.dk>",
            "to": ["mig@example.com"],
            "subject": "Emne",
            "text": "Krop",
        }
        return httpx.Response(200, json={"id": "abc123"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await email_client.send_email(to="mig@example.com", subject="Emne", text="Krop") is True


async def test_send_email_includes_html_when_given(monkeypatch):
    """Feature #204 — `html` er valgfri og lægges kun i payloaden når den
    rent faktisk er sat, så en almindelig ren-tekst-besked (fx en admin-
    broadcast) ikke sender et tomt/None `html`-felt til Resend."""

    async def fake_post(self, url, headers=None, json=None):
        assert json == {
            "from": "Voldby BIO <noreply@laces.dk>",
            "to": ["mig@example.com"],
            "subject": "Emne",
            "text": "Krop",
            "html": "<p>Krop</p>",
        }
        return httpx.Response(200, json={"id": "abc123"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert (
        await email_client.send_email(to="mig@example.com", subject="Emne", text="Krop", html="<p>Krop</p>")
        is True
    )


async def test_send_email_returns_false_on_rejected(monkeypatch):
    async def fake_post(self, url, headers=None, json=None):
        return httpx.Response(422, json={"message": "invalid"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await email_client.send_email(to="mig@example.com", subject="Emne", text="Krop") is False


async def test_send_email_raises_on_rate_limit(monkeypatch):
    async def fake_post(self, url, headers=None, json=None):
        return httpx.Response(429, json={"message": "rate limited"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(EmailRateLimitedError):
        await email_client.send_email(to="mig@example.com", subject="Emne", text="Krop")


async def test_send_email_returns_false_on_network_error(monkeypatch):
    async def fake_post(self, url, headers=None, json=None):
        raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await email_client.send_email(to="mig@example.com", subject="Emne", text="Krop") is False


async def test_test_connection_reports_ok_on_full_access_key(monkeypatch):
    async def fake_get(self, url, headers=None):
        assert url == "https://api.resend.com/api-keys"
        return httpx.Response(200, json={"data": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    ok, message = await email_client.test_connection()
    assert ok is True


async def test_test_connection_reports_ok_on_restricted_sending_key(monkeypatch):
    """Feature #197 — Resends anbefalede, mindst-privilegerede nøgletype
    ('sending_access') giver 401 restricted_api_key på GET /api-keys, selvom
    nøglen er fuldt gyldig til at sende med. Skal behandles som "virker",
    ikke som en ugyldig nøgle."""

    async def fake_get(self, url, headers=None):
        return httpx.Response(
            401,
            json={"name": "restricted_api_key", "message": "not allowed"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    ok, message = await email_client.test_connection()
    assert ok is True


async def test_test_connection_reports_failure_on_genuinely_invalid_key(monkeypatch):
    async def fake_get(self, url, headers=None):
        return httpx.Response(
            401, json={"name": "invalid_api_key", "message": "bad"}, request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    ok, message = await email_client.test_connection()
    assert ok is False


async def test_test_connection_reports_failure_when_no_key_set(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "")
    ok, message = await email_client.test_connection()
    assert ok is False


async def test_test_connection_returns_false_on_network_error(monkeypatch):
    async def fake_get(self, url, headers=None):
        raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    ok, message = await email_client.test_connection()
    assert ok is False
