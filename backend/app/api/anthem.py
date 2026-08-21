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


async def sse_stream(gen, is_disconnected, heartbeat_seconds: float):
    """Pakker en async generator af hændelser ind som SSE-tekstlinjer, med et
    periodisk heartbeat når der ikke er sket noget i `heartbeat_seconds`.

    BUGS.md #82 (opfølgning, Jan: "vi få ikke nogen log entry selv om vi se
    audio skift"): den oprindelige udgave brugte
    `asyncio.wait_for(gen.__anext__(), timeout=...)` — men `wait_for`
    ANNULLERER den underliggende opgave ved timeout. For en almindelig
    coroutine er det harmløst, men her afbryder annulleringen generatorens
    interne `await queue.get()` midt i alt, hvilket lukker generatoren
    PERMANENT (verificeret empirisk: enhver efterfølgende `.__anext__()`-kald
    rejser med det samme `StopAsyncIteration`, uanset om der reelt kommer nye
    hændelser senere). Praktisk betød det at streamen døde stille efter den
    FØRSTE `heartbeat_seconds` uden aktivitet — typisk længe før en admin
    overhovedet nåede at ændre noget på AVM'en.

    Rettelsen genbruger i stedet ÉN vedvarende baggrunds-opgave for "næste
    hændelse", og opretter kun en ny når den forrige rent faktisk er
    afsluttet. Et timeout på `asyncio.wait` (uden `wait_for`) lader den
    ventende opgave køre videre uafbrudt i baggrunden, så et senere
    update-event stadig når frem selvom det først dukker op efter et eller
    flere heartbeats."""
    next_task = asyncio.ensure_future(gen.__anext__())
    try:
        while True:
            if await is_disconnected():
                break
            done, _ = await asyncio.wait({next_task}, timeout=heartbeat_seconds)
            if not done:
                yield ": heartbeat\n\n"
                continue
            try:
                event = next_task.result()
            except StopAsyncIteration:
                break
            yield f"data: {json.dumps(event)}\n\n"
            next_task = asyncio.ensure_future(gen.__anext__())
    finally:
        # Vent på at annulleringen reelt er slået igennem i generatorens
        # frame, før den lukkes — ellers kan `gen.aclose()` ramme
        # generatoren mens den stadig er "i gang" med at afvikle
        # annulleringen af `next_task`, hvilket giver `RuntimeError:
        # aclose(): asynchronous generator is already running`. Bundet til
        # højst 2 sekunder: hvis selve OPRYDNINGEN sker mens denne coroutine
        # allerede er ved at blive annulleret udefra (fx test-teardown eller
        # klienten der lukker forbindelsen), kan endnu et `await` på et
        # tidspunkt hvor annulleringen stadig "leveres" i teorien selv blive
        # afbrudt igen og igen — en kort timeout her garanterer at oprydning
        # aldrig kan hænge for evigt, uanset den ydre kontekst.
        next_task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(next_task), timeout=2)
        except (asyncio.CancelledError, asyncio.TimeoutError, StopAsyncIteration):
            pass
        await gen.aclose()


@router.get("/diagnostics/stream", dependencies=[Depends(require_admin)])
async def stream_anthem_diagnostics(request: Request) -> StreamingResponse:
    # Preflight FØR StreamingResponse oprettes — se anthem_service.begin_session's
    # docstring for hvorfor: en fejl herfra skal give en rigtig 400/409, hvilket
    # kun virker hvis den rejses før status 200 og SSE-headers er sendt.
    anthem_service.begin_session()

    return StreamingResponse(
        sse_stream(anthem_service.stream_diagnostics(), request.is_disconnected, HEARTBEAT_SECONDS),
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
