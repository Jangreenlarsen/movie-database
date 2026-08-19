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
    ikke stille blive ved med at prøve i baggrunden."""
    return await anthemav.Connection.create(
        host=settings.anthem_host,
        port=settings.anthem_port,
        auto_reconnect=False,
        update_callback=update_callback,
    )


def snapshot(protocol) -> dict:
    """Læser de felter Jan bad om (input, volumen, audio_listening_mode,
    audio_input_format) plus et par ekstra diagnostisk nyttige felter
    (audio_input_channels_text, mute, power) ind i et almindeligt dict —
    klar til at sendes som SSE-payload eller optages i en log."""
    return {
        "power": protocol.power,
        "input_name": protocol.input_name,
        "input_number": protocol.input_number,
        "volume": protocol.volume,
        "mute": protocol.mute,
        "audio_listening_mode_text": protocol.audio_listening_mode_text,
        "audio_input_format_text": protocol.audio_input_format_text,
        "audio_input_channels_text": protocol.audio_input_channels_text,
    }
