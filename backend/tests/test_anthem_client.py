"""BUGS.md #82 — to reelle bugs i selve integrations-laget, fundet ved at
teste direkte mod produktionen (regel 16, "test i den faktiske
runtime-kontekst"): AVM70-diagnostikkens SSE-strøm gav 200 OK men leverede
aldrig noget som helst til klienten, uafhængigt af enhver proxy-konfiguration.

1. `anthemav.Connection.create(auto_reconnect=False, ...)` kalder kun selv
   `reconnect()` (som reelt åbner TCP-forbindelsen) når `auto_reconnect=True`
   — med `False` returneres en konstrueret, men ALDRIG forbundet,
   `Connection`, uden nogen fejl. `open_connection` skal derfor selv kalde
   `reconnect()` som et ekstra skridt.
2. Den ægte `anthemav.AVR`-klasse holder `mute`/`input_number`/`input_name`
   udelukkende på `protocol.zones[1]`, ikke som en genvej på `protocol`
   selv — `snapshot()` læste dem fejlagtigt direkte på `protocol`, hvilket
   gav en `AttributeError` på det allerførste snapshot-event.
"""

from app.integrations import anthem_client


class _FakeZone:
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


def test_snapshot_reads_mute_input_name_and_input_number_from_zone_one():
    """BUGS.md #82 — mute/input_number/input_name findes kun på
    protocol.zones[1], ikke direkte på protocol. Læses de forkert, kaster
    dette en AttributeError (det var netop den ægte fejl i produktionen)."""
    result = anthem_client.snapshot(_FakeProtocol())
    assert result["input_name"] == "Plex"
    assert result["input_number"] == 3
    assert result["mute"] is False
    # Top-level-felterne (ikke zone-specifikke) er uændrede.
    assert result["power"] is True
    assert result["volume"] == 42
    assert result["audio_listening_mode_text"] == "Dolby Atmos"


async def test_open_connection_explicitly_reconnects_after_create(monkeypatch):
    """BUGS.md #82 — anthemav.Connection.create(auto_reconnect=False, ...)
    springer selve TCP-forbindelsesforsøget helt over (det ligger kun i
    reconnect(), som create() kun selv kalder når auto_reconnect=True).
    open_connection skal derfor eksplicit kalde reconnect() bagefter, ellers
    "lykkes" kaldet altid uden nogensinde at have talt med enheden."""
    calls = {"reconnect": 0}

    class _FakeConn:
        def __init__(self):
            self.protocol = _FakeProtocol()

        async def reconnect(self):
            calls["reconnect"] += 1

    async def fake_create(*args, **kwargs):
        assert kwargs.get("auto_reconnect") is False
        return _FakeConn()

    monkeypatch.setattr(anthem_client.anthemav.Connection, "create", fake_create)

    conn = await anthem_client.open_connection(update_callback=lambda raw: None)

    assert calls["reconnect"] == 1
    assert conn is not None
