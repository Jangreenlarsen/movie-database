import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.integrations import tmdb_client
from app.repositories import poster_cache_repository

logger = logging.getLogger("moviedb")

# Feature #153 — kun de størrelser frontend rent faktisk beder om
# (posterUrl.js's cardPosterSize) cachess; forhindrer at en vilkårlig
# sti-parameter kan bruges til at spamme TMDb-kald med ugyldige størrelser.
ALLOWED_SIZES = {"w185", "w342", "w500"}


async def find_cached(db: AsyncIOMotorDatabase, size: str, path: str) -> tuple[bytes, str] | None:
    """Kun selve cache-opslaget — intet TMDb-kald. BUGS.md #80 (Jan,
    2026-08-20: "nåe man browser film i portal så kommer der lille pause
    være gang der skal hente en ny række film bileder") delte den
    tidligere `get_or_fetch` op i denne (hurtig, altid) og en baggrunds-
    hentning (`cache_in_background`, kun ved et cache-miss) — se
    `api.posters.get_poster` for hvordan de to bruges sammen."""
    if size not in ALLOWED_SIZES:
        return None
    cached = await poster_cache_repository.find_one(db, size, path)
    if cached is None:
        return None
    return bytes(cached["data"]), cached["content_type"]


async def cache_in_background(db: AsyncIOMotorDatabase, size: str, path: str) -> None:
    """Kaldes som en FastAPI `BackgroundTask` EFTER at et cache-miss allerede
    er besvaret med en redirect direkte til TMDb's CDN (se
    `api.posters.get_poster`) — henter og gemmer billedet, så enhver
    EFTERFØLGENDE forespørgsel på samme (size, path) rammer cachen med det
    samme, uden selv at opleve forsinkelsen ved denne allerførste hentning.
    Samme permanente cache som før (feature #153s offline-robusthed er
    uændret for alt der først er cachet); kun selve DENNE allerførste
    hentning sker nu parallelt med resten af siden i stedet for at blokere
    den. Fejl logges og ignoreres ellers stille (samme best-effort-filosofi
    som resten af TMDb-integrationen) — en mislykket baggrunds-cache
    betyder blot at næste forespørgsel også bliver en (stadig fungerende)
    redirect, ikke en fejl nogen ser."""
    try:
        fetched = await tmdb_client.fetch_poster_image(size, path)
        if fetched is None:
            return
        data, content_type = fetched
        await poster_cache_repository.insert(db, size, path, content_type, data)
    except Exception:
        logger.exception("Poster-cache: baggrunds-hentning af %s/%s fejlede", size, path)
