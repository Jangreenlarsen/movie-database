import logging

import httpx

from app.core.config import settings

BASE_URL = "https://www.omdbapi.com/"

logger = logging.getLogger("moviedb")


async def get_imdb_rating(imdb_id: str | None) -> float | None:
    """The *actual* IMDb rating (distinct from TMDb's own `vote_average`),
    keyed on the IMDb id TMDb already resolves via `external_ids`. Jan
    explicitly asked for the real IMDb score instead of TMDb's (2026-08-02).

    Never raises: this only ever enriches an already-successful TMDb fetch
    — a missing key, an unmatched title, or an OMDb outage all just mean
    "no IMDb rating available", so the caller falls back to TMDb's rating
    rather than the whole movie creation/sync failing (same nice-to-have
    philosophy as UPC/Discogs, see MOVIE_API_REFERENCE.md)."""
    if not settings.omdb_api_key or not imdb_id:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                BASE_URL, params={"i": imdb_id, "apikey": settings.omdb_api_key}
            )
    except httpx.HTTPError as exc:
        logger.warning("OMDb-opslag fejlede for %s: %s", imdb_id, exc)
        return None

    if response.status_code != 200:
        logger.info("OMDb-opslag returnerede %s for %s", response.status_code, imdb_id)
        return None

    data = response.json()
    if data.get("Response") == "False":
        logger.info("OMDb fandt intet for %s: %s", imdb_id, data.get("Error"))
        return None

    raw_rating = data.get("imdbRating")
    if not raw_rating or raw_rating == "N/A":
        return None

    try:
        return float(raw_rating)
    except ValueError:
        return None
