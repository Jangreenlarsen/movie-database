"""Feature #183 — AVM 70-diagnostik. Første SSE-endpoint i appen (resten af
appens "live" visninger bruger polling, fx `MonitorSection`s 10s-interval)
— valgt her fordi selve pointen med diagnostikken er at se den reelle
timing mellem AVM70-hændelser, som polling ville udjævne. Rå
`StreamingResponse` frem for et ekstra SSE-bibliotek — formatet
(`data: <json>\\n\\n`, `: heartbeat\\n\\n`) er få linjer og giver fuld
kontrol over disconnect-håndteringen.

BUGS.md #82: produktionen når appen udefra via `movie.laces.dk`, gennem
en SEPARAT nginx-reverse-proxy-VM foran Caddy (se DEPLOYMENT.md,
"Offentlig adgang") — ikke dokumenteret som en del af selve appens
Caddyfile. nginx bufferer som standard hele response-body'en før den
videresendes til klienten (`proxy_buffering on`), hvilket for en
uendelig SSE-strøm betyder at browseren aldrig modtager NOGET (heller
ikke det indledende snapshot-event eller heartbeats) — kun HTTP 200 og
headerne, som allerede sendes før body'en overhovedet begynder. Det
matcher præcis Jans observation: statuskoden i DevTools var 200, men
knappen skiftede aldrig reelt til "live" og faldt til sidst tavst
tilbage uden nogen fejlbesked, når nginx til sidst lukkede den bufrede,
tomme forbindelse. `X-Accel-Buffering: no` er nginx's egen,
standardiserede måde for en upstream-app at bede om at netop ÉT
specifikt svar IKKE skal bufferes — kræver ingen ændring af selve
nginx-VM'ens konfiguration (som er git-ignoreret og uden for dette
repos kontrol, jf. DEPLOYMENT.md)."""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user, require_admin
from app.services import anthem_service

logger = logging.getLogger("moviedb")

router = APIRouter(prefix="/api/anthem", tags=["anthem"], dependencies=[Depends(get_current_user)])

# Sendt som en SSE-kommentarlinje når der ikke er sket noget i AVM'en i
# HEARTBEAT_SECONDS — holder forbindelsen i live gennem enhver mellemliggende
# proxy/timeout, uden at det tolkes som et rigtigt hændelses-event.
HEARTBEAT_SECONDS = 15


@router.get("/diagnostics/stream", dependencies=[Depends(require_admin)])
async def stream_anthem_diagnostics(request: Request) -> StreamingResponse:
    # Preflight FØR StreamingResponse oprettes — se anthem_service.begin_session's
    # docstring for hvorfor: en fejl herfra skal give en rigtig 400/409, hvilket
    # kun virker hvis den rejses før status 200 og SSE-headers er sendt.
    anthem_service.begin_session()

    async def event_source():
        gen = anthem_service.stream_diagnostics()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(gen.__anext__(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                except StopAsyncIteration:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await gen.aclose()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            # Se modulets docstring (BUGS.md #82) — beder nginx-hoppet foran
            # Caddy om at IKKE buffere netop dette svar. Uden denne header når
            # intet fra strømmen (heller ikke det indledende snapshot) frem
            # til klienten, før nginx til sidst lukker den bufrede forbindelse.
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )
