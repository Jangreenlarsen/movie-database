from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_database
from app.integrations.tmdb_client import IMAGE_HOST
from app.services import poster_cache_service

# Feature #153 — permanent lokal poster-cache. Bevidst UDEN login-krav,
# samme princip som TMDb's egen CDN havde før (ren billed-visning, ingen
# følsom data): postere skal også kunne vises på den offentlige /bio-side
# for uindloggede besøgende (CinemaPublic.jsx).
router = APIRouter(prefix="/api/posters", tags=["posters"])


@router.get("/{size}/{path:path}")
async def get_poster(
    size: str,
    path: str,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Response:
    """BUGS.md #80 (Jan, 2026-08-20: "nåe man browser film i portal så
    kommer der lille pause være gang der skal hente en ny række film
    bileder") — et cache-hit (langt de fleste kald, når først biblioteket er
    varmet op) serveres uændret direkte fra MongoDB. Et cache-MISS ramte
    tidligere `poster_cache_service.get_or_fetch`, som blokerede hele
    forespørgslen på en synkron TMDb-hentning + Mongo-skrivning, før noget
    som helst blev returneret — markant langsommere end et direkte CDN-hit,
    og mærkbart som en pause når en hel ny række postere (aldrig set før i
    den størrelse) alle ramte cache-miss cirka samtidig.

    Nu redirectes et cache-miss i stedet med det samme direkte til TMDb's
    CDN (samme hastighed som før poster-cachen fandtes overhovedet), mens
    selve cachningen sker som en `BackgroundTask` efter svaret er sendt —
    enhver EFTERFØLGENDE forespørgsel på samme (size, path) rammer cachen
    som normalt. Ingen regression for feature #153s oprindelige
    offline-formål: et allerede cachet billede afhænger stadig aldrig af
    TMDb; kun det allerførste, aldrig-sete cache-miss opfører sig
    anderledes (hurtigere, ikke langsommere)."""
    cached = await poster_cache_service.find_cached(db, size, path)
    if cached is not None:
        data, content_type = cached
        return Response(
            content=data,
            media_type=content_type,
            # Cachet permanent i backend'en, og (size, path) peger altid på
            # nøjagtig samme bytes — så browseren må også gerne gemme den for altid.
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    if size not in poster_cache_service.ALLOWED_SIZES:
        return Response(status_code=404)

    background_tasks.add_task(poster_cache_service.cache_in_background, db, size, path)
    return RedirectResponse(f"{IMAGE_HOST}/{size}/{path}", status_code=302)
