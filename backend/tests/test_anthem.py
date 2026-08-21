"""Feature #183 (Jan: "lave en dianostik modul i portal under settings ...
skal vi have en funktion som læser alle relavante sætting ud og det er
input, vol, audio_listening_mode, audio_input_format og en status live
updatering på update_callback"). Dækker service-laget direkte (den faktiske
hændelses-strøm) og API-lagets preflight-fejl (admin-only, ikke
konfigureret, session optaget) — selve SSE-transporten testes ikke
ende-til-ende her, se `anthem_service.stream_diagnostics`s docstring for
hvorfor: en fejl efter `StreamingResponse` er oprettet kan ikke længere
blive en HTTP-statuskode.
"""

import pytest

from app.core.config import settings
from app.core.errors import AnthemNotConfiguredError, AnthemSessionBusyError
from app.integrations import anthem_client
from app.services import anthem_service


class _FakeZone:
    """BUGS.md #82: den ægte `anthemav.AVR`-klasse holder kun `mute`,
    `input_number` og `input_name` på `protocol.zones[1]` — IKKE som en
    genvej direkte på `protocol`. Denne fake mangled tidligere det, hvilket
    lod en `AttributeError` i `anthem_client.snapshot` (læste fejlagtigt
    `protocol.input_name` i stedet for `protocol.zones[1].input_name`) gå
    helt uopdaget gennem testsuiten."""

    def __init__(self):
        self.input_name = "Plex"
        self.input_number = 3
        self.mute = False


class _FakeProtocol:
    def __init__(self):
        self.power = True
        self.volume = 42
        self.audio_listening_mode_text = "Dolby Atmos"
        self.audio_input_format_text = "Dolby Atmos"
        self.audio_input_channels_text = "7.1-channel"
        self.zones = {1: _FakeZone()}


class _FakeConnection:
    def __init__(self):
        self.protocol = _FakeProtocol()
        self.closed = False

    def close(self):
        self.closed = True


def _configure(monkeypatch):
    monkeypatch.setattr(settings, "anthem_host", "192.168.1.60")
    monkeypatch.setattr(settings, "anthem_port", 14999)


# --- begin_session (preflight) ----------------------------------------------


def test_begin_session_requires_configuration(monkeypatch):
    monkeypatch.setattr(settings, "anthem_host", "")
    with pytest.raises(AnthemNotConfiguredError):
        anthem_service.begin_session()


def test_begin_session_rejects_a_second_concurrent_session(monkeypatch):
    _configure(monkeypatch)
    anthem_service.begin_session()
    with pytest.raises(AnthemSessionBusyError):
        anthem_service.begin_session()


def test_begin_session_succeeds_again_after_end_session(monkeypatch):
    _configure(monkeypatch)
    anthem_service.begin_session()
    anthem_service._end_session()
    anthem_service.begin_session()  # skal ikke rejse


# --- API: admin-only + preflight-fejl mappet til rigtige statuskoder -------


async def test_stream_endpoint_requires_admin(client, monkeypatch):
    _configure(monkeypatch)
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        register = await standard_client.post(
            "/api/auth/register", json={"username": "notadmin183", "password": "testpassword123"}
        )
        await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})
        await client.patch(f"/api/users/{register.json()['id']}/role", json={"role": "standard"})

        response = await standard_client.get("/api/anthem/diagnostics/stream")
        assert response.status_code == 403


async def test_stream_endpoint_returns_400_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "anthem_host", "")
    response = await client.get("/api/anthem/diagnostics/stream")
    assert response.status_code == 400
    assert "ikke konfigureret" in response.json()["detail"]


async def test_stream_endpoint_returns_409_when_a_session_is_already_active(client, monkeypatch):
    _configure(monkeypatch)
    anthem_service.begin_session()
    try:
        response = await client.get("/api/anthem/diagnostics/stream")
        assert response.status_code == 409
    finally:
        anthem_service._end_session()


async def test_stream_endpoint_asks_the_public_nginx_hop_not_to_buffer_the_response(client, monkeypatch):
    """BUGS.md #82: appen nås udefra via `movie.laces.dk` gennem en separat
    nginx-VM (se DEPLOYMENT.md) foran Caddy. nginx bufferer som standard hele
    response-body'en, hvilket for en uendelig SSE-strøm betyder intet nogensinde
    når frem til klienten — knappen skiftede aldrig reelt til "live" i
    produktion. `X-Accel-Buffering: no` er nginx's egen, standardiserede måde
    for en upstream-app at bede om at netop dette svar ikke skal bufferes."""
    _configure(monkeypatch)
    fake_conn = _FakeConnection()

    async def fake_open_connection(update_callback):
        return fake_conn

    monkeypatch.setattr(anthem_client, "open_connection", fake_open_connection)

    async with client.stream("GET", "/api/anthem/diagnostics/stream") as response:
        assert response.status_code == 200
        assert response.headers["x-accel-buffering"] == "no"


# --- stream_diagnostics (selve hændelses-strømmen) --------------------------


async def test_stream_yields_an_initial_snapshot(monkeypatch):
    _configure(monkeypatch)
    fake_conn = _FakeConnection()

    async def fake_open_connection(update_callback):
        return fake_conn

    monkeypatch.setattr(anthem_client, "open_connection", fake_open_connection)

    gen = anthem_service.stream_diagnostics()
    try:
        event = await gen.__anext__()
        assert event["type"] == "snapshot"
        assert event["input_name"] == "Plex"
        assert event["volume"] == 42
        assert event["audio_listening_mode_text"] == "Dolby Atmos"
        assert event["audio_input_format_text"] == "Dolby Atmos"
    finally:
        await gen.aclose()


async def test_stream_yields_an_update_event_when_the_callback_fires(monkeypatch):
    _configure(monkeypatch)
    fake_conn = _FakeConnection()
    captured_callback = {}

    async def fake_open_connection(update_callback):
        captured_callback["fn"] = update_callback
        return fake_conn

    monkeypatch.setattr(anthem_client, "open_connection", fake_open_connection)

    gen = anthem_service.stream_diagnostics()
    try:
        await gen.__anext__()  # snapshot
        fake_conn.protocol.volume = 55
        captured_callback["fn"]("Z1VOL55")

        event = await gen.__anext__()
        assert event["type"] == "update"
        assert event["raw"] == "Z1VOL55"
        assert event["volume"] == 55
    finally:
        await gen.aclose()


async def test_stream_closes_the_connection_and_releases_the_session_on_aclose(monkeypatch):
    _configure(monkeypatch)
    fake_conn = _FakeConnection()

    async def fake_open_connection(update_callback):
        return fake_conn

    monkeypatch.setattr(anthem_client, "open_connection", fake_open_connection)

    anthem_service.begin_session()
    gen = anthem_service.stream_diagnostics()
    await gen.__anext__()
    await gen.aclose()

    assert fake_conn.closed is True
    # Frigivet igen — en ny session kan startes uden 409.
    anthem_service.begin_session()


async def test_stream_yields_an_error_event_when_the_connection_fails(monkeypatch):
    _configure(monkeypatch)

    async def fake_open_connection(update_callback):
        raise OSError("Connection refused")

    monkeypatch.setattr(anthem_client, "open_connection", fake_open_connection)

    gen = anthem_service.stream_diagnostics()
    event = await gen.__anext__()
    assert event["type"] == "error"
    assert "Kunne ikke forbinde" in event["message"]

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()
