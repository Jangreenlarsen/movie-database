"""BUGS.md #113 — e-mails til mange modtagere må ikke gå tabt ved Resends
rate-limit (standard 2 kald/s). `_send_emails` holder et tempo mellem
kaldene og prøver én gang igen efter `Retry-After`, før den giver op."""

import httpx
import pytest

from app.core.config import settings
from app.core.errors import EmailRateLimitedError
from app.integrations import email_client
from app.services import message_service


def _recipients(*names):
    return [{"username": n, "_email": f"{n}@example.com"} for n in names]


@pytest.fixture
def resend(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(message_service.asyncio, "sleep", fake_sleep)
    return sleeps


async def test_spacing_between_recipients(resend, monkeypatch):
    monkeypatch.setattr(message_service, "EMAIL_SPACING_SECONDS", 0.6)
    sent = []

    async def ok(to, subject, text, html=None):
        sent.append(to)
        return True

    monkeypatch.setattr(email_client, "send_email", ok)
    await message_service._send_emails(_recipients("a", "b", "c"), "Emne", "Krop")
    assert sent == ["a@example.com", "b@example.com", "c@example.com"]
    # Pause mellem kaldene, ikke før det første.
    assert resend == [0.6, 0.6]


async def test_one_rate_limit_is_retried_and_nobody_is_skipped(resend, monkeypatch):
    calls = []

    async def flaky(to, subject, text, html=None):
        calls.append(to)
        if len(calls) == 2:
            raise EmailRateLimitedError(retry_after=1.5)
        return True

    monkeypatch.setattr(email_client, "send_email", flaky)
    await message_service._send_emails(_recipients("a", "b", "c"), "Emne", "Krop")
    assert calls == ["a@example.com", "b@example.com", "b@example.com", "c@example.com"]
    assert 1.5 in resend


async def test_a_long_retry_after_stops_without_waiting(resend, monkeypatch):
    calls = []

    async def blocked(to, subject, text, html=None):
        calls.append(to)
        raise EmailRateLimitedError(retry_after=120)

    monkeypatch.setattr(email_client, "send_email", blocked)
    await message_service._send_emails(_recipients("a", "b"), "Emne", "Krop")
    assert calls == ["a@example.com"]
    assert 120 not in resend


async def test_email_client_passes_on_retry_after(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "noreply@laces.dk")

    async def fake_post(self, url, **kwargs):
        return httpx.Response(429, headers={"retry-after": "2"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(EmailRateLimitedError) as info:
        await email_client.send_email(to="x@example.com", subject="s", text="t")
    assert info.value.retry_after == 2.0


@pytest.mark.parametrize("value", [None, "", "   ", "Wed, 21 Oct 2026 07:28:00 GMT", "-1"])
def test_unusable_retry_after_values_give_none(value):
    assert email_client._retry_after_seconds(value) is None
