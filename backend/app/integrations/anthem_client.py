"""Anthem AVM 70-integration (feature #183, Jan: "lave en undersøgelse af
hvad mulighed vi har for at remote kontrollere AVM70").

Tynd wrapper om det eksterne `anthemav`-bibliotek (asyncio, ren tekst-
protokol over TCP port 14999, understøtter eksplicit AVM 70). Kun
læse-adgang indtil videre — dette er diagnostik-fasen (feature #183), ikke
den endelige workflow-automation, som først bygges når Jan har brugt
diagnostikken til at forstå enhedens faktiske timing.

AVM 70 accepterer kun én netværksklient ad gangen — se
`app.services.anthem_service` for enkelt-session-håndhævelsen.
"""

from typing import Callable

import anthemav

from app.core.config import settings


def is_configured() -> bool:
    return bool(settings.anthem_host)


async def open_connection(update_callback: Callable[[str], None]) -> anthemav.Connection:
    """Åbner én forbindelse til AVM70. Kalderen ejer hele livscyklussen
    (lukning via `.close()`).

    `auto_reconnect=False` er bevidst: bibliotekets eget genforbindelses-loop
    forsøger i det uendelige uden nogen timeout, hvilket ville få dette kald
    til at hænge for evigt hvis AVM'en er slukket eller IP'en er forkert. En
    kortvarig diagnostik-session skal fejle med det samme (rejser `OSError`),
    ikke stille blive ved med at prøve i baggrunden.

    BUGS.md #82: `anthemav.Connection.create()` kalder kun selv
    `conn.reconnect()` (den funktion der reelt åbner TCP-forbindelsen) når
    `auto_reconnect=True` — med `False` returnerer `create()` bare en
    konstrueret, men ALDRIG forbundet, `Connection` med det samme, uden
    fejl. Diagnostikken troede den var forbundet (intet `OSError` blev
    rejst), mens den reelt aldrig havde talt med enheden. `reconnect()`
    kaldes derfor eksplicit herfra som det ekstra skridt — med
    `auto_reconnect=False` foretager DEN kun ét forsøg og rejser `OSError`
    med det samme ved fejl (ingen af bibliotekets egne retry-løkke), præcis
    den fail-fast-adfærd denne funktion altid har antaget den fik."""
    conn = await anthemav.Connection.create(
        host=settings.anthem_host,
        port=settings.anthem_port,
        auto_reconnect=False,
        update_callback=update_callback,
    )
    await conn.reconnect()
    return conn


def snapshot(protocol) -> dict:
    """Læser de felter Jan bad om (input, volumen, audio_listening_mode,
    audio_input_format) plus et par ekstra diagnostisk nyttige felter
    (audio_input_channels_text, mute, power) ind i et almindeligt dict —
    klar til at sendes som SSE-payload eller optages i en log.

    BUGS.md #82: `anthemav`s `AVR`-klasse (selve `protocol`) delegerer kun
    `power`/`volume`/`audio_*`-felterne til zone 1 internt — `mute`,
    `input_number` og `input_name` findes UDELUKKENDE på `protocol.zones[1]`,
    ikke som en genvej på `protocol` selv. At læse dem direkte på `protocol`
    gav `AttributeError` for `input_name` allerede på det allerførste
    snapshot-event, hvilket droppede hele SSE-strømmen midt i en
    StreamingResponse (200-status og headers allerede sendt) — set fra
    klienten som en forbindelse der aldrig leverede noget som helst, uden
    nogen fejlbesked. Fanget for sent til at kunne mappes til en pæn HTTP-
    fejl; roden var slet ikke opdaget af testsuiten, da `_FakeProtocol` i
    `test_anthem.py` sætter disse som almindelige attributter direkte på
    et fake-objekt uden zone-strukturen, og derfor aldrig ramte samme fejl
    som den ægte `anthemav`-klasse."""
    zone = protocol.zones[1]
    return {
        "power": protocol.power,
        "input_name": zone.input_name,
        "input_number": zone.input_number,
        "volume": protocol.volume,
        "mute": zone.mute,
        "audio_listening_mode_text": protocol.audio_listening_mode_text,
        "audio_input_format_text": protocol.audio_input_format_text,
        "audio_input_channels_text": protocol.audio_input_channels_text,
    }
