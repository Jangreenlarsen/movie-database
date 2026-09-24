import logging
import re

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.integrations import tmdb_client
from app.repositories import poster_cache_repository

logger = logging.getLogger("moviedb")

# Feature #153 — kun de størrelser frontend rent faktisk beder om
# (posterUrl.js's cardPosterSize) cachess; forhindrer at en vilkårlig
# sti-parameter kan bruges til at spamme TMDb-kald med ugyldige størrelser.
ALLOWED_SIZES = {"w185", "w342", "w500"}

# BUGS.md #108 — endpointet er offentligt (ingen login). En TMDb-poster er
# altid ét filnavn (fx "kqjL17yufvn9OVLyXYpvtyrFfak.jpg"); uden dette tjek
# kunne "../../" i stien få serveren til at hente og permanent gemme andre
# filer fra image.tmdb.org. Kun rasterbilleder gemmes/serveres — aldrig SVG
# eller HTML, som ville kunne køre script fra vores eget domæne.
_VALID_PATH = re.compile(r"^[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)$")
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def is_valid_request(size: str, path: str) -> bool:
    return size in ALLOWED_SIZES and bool(_VALID_PATH.match(path))


def _base_content_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


async def find_cached(db: AsyncIOMotorDatabase, size: str, path: str) -> tuple[bytes, str] | None:
    """Kun selve cache-opslaget — intet TMDb-kald. BUGS.md #80 (Jan,
    2026-08-20: "nåe man browser film i portal så kommer der lille pause
    være gang der skal hente en ny række film bileder") delte den
    tidligere `get_or_fetch` op i denne (hurtig, altid) og en baggrunds-
    hentning (`cache_in_background`, kun ved et cache-miss) — se
    `api.posters.get_poster` for hvordan de to bruges sammen."""
    if not is_valid_request(size, path):
        return None
    cached = await poster_cache_repository.find_one(db, size, path)
    if cached is None:
        return None
    content_type = _base_content_type(cached["content_type"])
    if content_type not in ALLOWED_CONTENT_TYPES:
        return None
    return bytes(cached["data"]), content_type


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
    if not is_valid_request(size, path):
        return
    try:
        fetched = await tmdb_client.fetch_poster_image(size, path)
        if fetched is None:
            return
        data, content_type = fetched
        content_type = _base_content_type(content_type)
        if content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(
                "Poster-cache: afviste %s/%s med content-type %r", size, path, content_type
            )
            return
        await poster_cache_repository.insert(db, size, path, content_type, data)
    except Exception:
        logger.exception("Poster-cache: baggrunds-hentning af %s/%s fejlede", size, path)
