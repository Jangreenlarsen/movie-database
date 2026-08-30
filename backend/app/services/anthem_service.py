"""Feature #183 — AVM 70-diagnostik.

Live overvågning af input/volumen/audio_listening_mode/audio_input_format
via Server-Sent Events, drevet af `anthemav`s `update_callback`-hændelser —
til at opbygge erfaring med enhedens faktiske opførsel/timing, før den
egentlige automation (starte film i Plex → sæt audio-mode → vent til
stabil → unmute) bygges. Se `app.integrations.anthem_client` for selve
protokol-wrapperen.

Kun ÉN diagnostik-session kan være aktiv ad gangen — AVM 70 accepterer kun
én netværksklient. `_session_active` er et almindeligt modul-globalt
bool-flag, ikke en `asyncio.Lock`: tjek og sætning sker i samme synkrone
kodeblok uden noget `await` imellem, hvilket allerede er atomart under
asyncios ét-tråds kooperative scheduling — en lås ville kun tilføje
kompleksitet uden at løse noget en almindelig boolean ikke allerede gør her.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from app.core.config import settings
from app.core.errors import AnthemNotConfiguredError, AnthemSessionBusyError
from app.integrations import anthem_client

logger = logging.getLogger("moviedb")

_session_active = False


def begin_session() -> None:
    """Preflight-tjek — skal kaldes af API-laget FØR en `StreamingResponse`
    oprettes. En FastAPI `StreamingResponse` har allerede committet status
    200 i det øjeblik dens generator begynder at køre, så en fejl der skal
    give en rigtig HTTP-statuskode (400/409) skal rejses her, ikke inde fra
    selve `stream_diagnostics`."""
    global _session_active
    if not anthem_client.is_configured():
        raise AnthemNotConfiguredError()
    if _session_active:
        raise AnthemSessionBusyError()
    _session_active = True


def _end_session() -> None:
    global _session_active
    _session_active = False


async def test_connection() -> tuple[bool, str]:
    """Feature #212 (Jan: "kan vi ikke lige få en test funktion ind i api
    config for AVM70 også sådan at vi kan testet den på samme hvilkor som
    api keys") — genbruger `anthem_client.open_connection` uændret: en
    ægte, kortvarig TCP-forbindelse til enheden, lukket med det samme igen
    (samme mønster som de øvrige integrations-klienters `test_connection`,
    se `system_settings_service._TEST_CONNECTION_CLIENTS`). Lever i
    service-laget, ikke i `anthem_client` selv, fordi den skal tjekke
    `_session_active` først — AVM70 accepterer kun én netværksklient ad
    gangen (modulets docstring), så et testforsøg mens en rigtig
    diagnostik-session kører ville ellers fejle med en vildledende
    "kunne ikke forbinde"-besked i stedet for den reelle årsag."""
    if not anthem_client.is_configured():
        return False, "Anthem-enhedens IP/host er ikke sat"
    if _session_active:
        return False, "Kan ikke teste lige nu — en diagnostik-session er allerede i gang"
    try:
        conn = await anthem_client.open_connection(lambda _raw: None)
    except OSError as exc:
        return False, f"Kunne ikke forbinde til {settings.anthem_host}:{settings.anthem_port} ({exc})"
    conn.close()
    return True, f"Forbundet til Anthem-enheden på {settings.anthem_host}:{settings.anthem_port}"


def _event(event_type: str, protocol, raw: str | None) -> dict:
    return {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw": raw,
        **anthem_client.snapshot(protocol),
    }


async def stream_diagnostics() -> AsyncGenerator[dict, None]:
    """Selve hændelses-strømmen. Antager `begin_session()` allerede er
    kaldt og lykkedes — se dens docstring for hvorfor preflight-tjekket er
    adskilt herfra.

    En fejlet forbindelse (AVM slukket, forkert IP) rapporteres som et
    almindeligt `{"type": "error", ...}`-event i selve strømmen i stedet
    for en HTTP-fejlkode — på dette tidspunkt er 200-status og SSE-headers
    allerede sendt til klienten, så det er den eneste måde fejlen kan nå
    frem på. `finally` frigiver altid sessionen, uanset hvordan generatoren
    afsluttes (klient lukker fanen, netværksfejl, eksplicit stop) —
    CLAUDE.md regel 16."""
    queue: asyncio.Queue[str] = asyncio.Queue()

    def on_update(raw: str) -> None:
        queue.put_nowait(raw)

    try:
        try:
            conn = await anthem_client.open_connection(on_update)
        except OSError as exc:
            logger.warning("Anthem-diagnostik: kunne ikke forbinde (%s)", exc)
            yield {
                "type": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"Kunne ikke forbinde til AVM70 på {settings.anthem_host}:{settings.anthem_port} ({exc})",
            }
            return

        try:
            yield _event("snapshot", conn.protocol, raw=None)
            while True:
                raw = await queue.get()
                yield _event("update", conn.protocol, raw=raw)
        finally:
            conn.close()
    finally:
        _end_session()
