import logging

import httpx

from app.core.config import settings
from app.integrations.text_cleanup import clean_bracketed_title

BASE_URL = "https://api.discogs.com/database/search"
USER_AGENT = "MovieDatabaseApp/1.0"

logger = logging.getLogger("moviedb")


def _strip_artist_prefix(title: str) -> str:
    """Discogs formats nearly every release as "Artist - Title" (even for
    movies, where "Artist" is often "Various" or a studio name) — drop that
    prefix so the remainder is a cleaner TMDb search query."""
    _, separator, rest = title.partition(" - ")
    return rest if separator and rest else title


async def lookup_title(barcode: str) -> str | None:
    """Best-effort fallback UPC/EAN -> title guess when UPCitemdb has no
    match — Discogs' community-catalogued database covers DVD/Blu-ray/VHS
    releases (including European EAN codes) that UPCitemdb's US-centric
    trial tier often misses. Never raises: nice-to-have prefill, not a
    critical path (see MOVIE_API_REFERENCE.md)."""
    params = {"barcode": barcode}
    if settings.discogs_token:
        params["token"] = settings.discogs_token

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                BASE_URL, params=params, headers={"User-Agent": USER_AGENT}
            )
    except httpx.HTTPError as exc:
        logger.warning("Discogs lookup failed for %s: %s", barcode, exc)
        return None

    if response.status_code != 200:
        logger.info("Discogs lookup returned %s for %s", response.status_code, barcode)
        return None

    results = response.json().get("results") or []
    if not results:
        logger.info("Discogs: intet match for %s", barcode)
        return None

    raw_title = results[0].get("title")
    if not raw_title:
        logger.info("Discogs: match uden titel-felt for %s", barcode)
        return None

    title = clean_bracketed_title(_strip_artist_prefix(raw_title))
    logger.info("Discogs: %s -> %r", barcode, title)
    return title


async def test_connection() -> tuple[bool, str]:
    """Feature #75 — Discogs works fine without a token (just a lower rate
    limit), so an empty token isn't itself a failure; but a genuinely wrong
    token is rejected with a 401, which is reported clearly."""
    if not settings.discogs_token:
        return True, "Intet token sat — Discogs virker stadig, blot med lavere rate-limit"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                BASE_URL,
                params={"q": "test", "token": settings.discogs_token},
                headers={"User-Agent": USER_AGENT},
            )
    except httpx.HTTPError as exc:
        return False, f"Netværksfejl: {exc}"

    if response.status_code == 401:
        return False, "Discogs afviste token'et (ugyldigt)"
    if response.status_code != 200:
        return False, f"Uventet svar (HTTP {response.status_code})"
    return True, "Virker"
