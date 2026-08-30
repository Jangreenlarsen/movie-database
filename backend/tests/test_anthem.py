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

import asyncio

import pytest

from app.api.anthem import sse_stream, stream_anthem_diagnostics
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


async def test_stream_endpoint_asks_the_public_nginx_hop_not_to_buffer_the_response(monkeypatch):
    """BUGS.md #82: appen nås udefra via `movie.laces.dk` gennem en separat
    nginx-VM (se DEPLOYMENT.md) foran Caddy. nginx bufferer som standard hele
    response-body'en, hvilket for en uendelig SSE-strøm betyder intet nogensinde
    når frem til klienten. `X-Accel-Buffering: no` er nginx's egen,
    standardiserede måde for en upstream-app at bede om at netop dette svar
    ikke skal bufferes.

    Kalder route-funktionen direkte i stedet for at gå via en levende
    httpx-klient: strømmen er bevidst designet til at køre for evigt (feature
    #183), og `httpx.ASGITransport`s test-simulering af et klient-disconnect
    viste sig ikke pålideligt at afslutte den bagvedliggende opgave — kun
    selve headerne på det returnerede `StreamingResponse`-objekt er
    testværdige her, og de er tilgængelige uden nogensinde at skulle
    iterere/afvikle selve body'en."""
    _configure(monkeypatch)
    fake_conn = _FakeConnection()

    async def fake_open_connection(update_callback):
        return fake_conn

    monkeypatch.setattr(anthem_client, "open_connection", fake_open_connection)

    class _FakeRequest:
        async def is_disconnected(self):
            return False

    try:
        response = await stream_anthem_diagnostics(_FakeRequest())
    finally:
        anthem_service._end_session()

    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-cache"
    assert response.media_type == "text/event-stream"


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


# --- sse_stream (heartbeat/timeout-wrapperen) -------------------------------


async def test_sse_stream_delivers_a_late_event_after_one_or_more_heartbeats():
    """BUGS.md #82 (Jan: "vi få ikke nogen log entry selv om vi se audio
    skift"). Den oprindelige `asyncio.wait_for(gen.__anext__(), ...)`
    annullerede generatorens interne `await` ved hvert heartbeat-timeout,
    hvilket lukkede den permanent — et event der først opstod EFTER det
    første heartbeat blev derfor aldrig leveret. Denne test reproducerer
    netop det: en hændelse der ankommer efter to heartbeats skal stadig nå
    frem, og strømmen skal fortsætte bagefter (endnu en hændelse leveres)."""

    async def slow_gen():
        yield "first"
        await asyncio.sleep(0.2)  # længere end heartbeat_seconds herunder
        yield "late-update"
        yield "immediately-after"

    async def never_disconnected():
        return False

    chunks = []
    stream = sse_stream(slow_gen(), never_disconnected, heartbeat_seconds=0.05)
    async for chunk in stream:
        chunks.append(chunk)
        # Nok til: første event, mindst ét heartbeat, den sene opdatering,
        # og den umiddelbart efterfølgende hændelse.
        if chunks.count("data: \"late-update\"\n\n") and chunks.count("data: \"immediately-after\"\n\n"):
            break

    assert "data: \"first\"\n\n" in chunks
    assert ": heartbeat\n\n" in chunks  # bekræfter at mindst ét heartbeat reelt blev sendt undervejs
    assert "data: \"late-update\"\n\n" in chunks
    assert "data: \"immediately-after\"\n\n" in chunks


async def test_sse_stream_stops_when_the_client_disconnects():
    async def infinite_gen():
        while True:
            await asyncio.sleep(10)
            yield "never"

    calls = {"n": 0}

    async def disconnect_after_first_check():
        calls["n"] += 1
        return calls["n"] > 1

    chunks = []
    async for chunk in sse_stream(infinite_gen(), disconnect_after_first_check, heartbeat_seconds=0.05):
        chunks.append(chunk)

    assert chunks == [": heartbeat\n\n"]  # ét heartbeat, saa opdages disconnect og streamen slutter


# --- test_connection (feature #212) ------------------------------------------


async def test_test_connection_fails_clearly_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "anthem_host", "")

    ok, message = await anthem_service.test_connection()

    assert ok is False
    assert "ikke sat" in message


async def test_test_connection_succeeds_and_closes_the_connection(monkeypatch):
    _configure(monkeypatch)
    fake_conn = _FakeConnection()

    async def fake_open_connection(update_callback):
        return fake_conn

    monkeypatch.setattr(anthem_client, "open_connection", fake_open_connection)

    ok, message = await anthem_service.test_connection()

    assert ok is True
    assert "192.168.1.60" in message
    assert fake_conn.closed is True


async def test_test_connection_reports_a_connection_failure(monkeypatch):
    _configure(monkeypatch)

    async def fake_open_connection(update_callback):
        raise OSError("Connection refused")

    monkeypatch.setattr(anthem_client, "open_connection", fake_open_connection)

    ok, message = await anthem_service.test_connection()

    assert ok is False
    assert "Connection refused" in message


async def test_test_connection_refuses_while_a_diagnostics_session_is_active(monkeypatch):
    _configure(monkeypatch)
    anthem_service.begin_session()
    try:
        ok, message = await anthem_service.test_connection()
    finally:
        anthem_service._end_session()

    assert ok is False
    assert "allerede i gang" in message
