import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("moviedb")


def _base_url() -> str:
    return settings.plex_server_url.rstrip("/")


def _headers() -> dict:
    return {"X-Plex-Token": settings.plex_token, "Accept": "application/json"}


async def find_movie(tmdb_id: int | None, title: str | None, year: int | None) -> dict | None:
    """Best-effort match against the user's own Plex server. Returns
    {"rating_key": str, "machine_identifier": str} or None — never raises.
    A missing/unreachable/misconfigured Plex server degrades to "not
    available" rather than breaking the movie detail view, same philosophy
    as the UPC/Discogs lookups (MOVIE_API_REFERENCE.md).

    Matching strategy: prefer an exact TMDb-id match via the item's `Guid`
    list (works with Plex's newer universal agent and most TMDb-based
    agents); fall back to an exact title+year match if no GUID hit — Plex's
    GUID format varies across agent versions and isn't guaranteed present."""
    if not settings.plex_server_url or not settings.plex_token or not title:
        return None

    try:
        async with httpx.AsyncClient(timeout=6) as client:
            identity_response = await client.get(f"{_base_url()}/identity", headers=_headers())
            if identity_response.status_code != 200:
                return None
            machine_identifier = (
                identity_response.json().get("MediaContainer", {}).get("machineIdentifier")
            )

            search_response = await client.get(
                f"{_base_url()}/search", headers=_headers(), params={"query": title}
            )
            if search_response.status_code != 200:
                return None
            results = search_response.json().get("MediaContainer", {}).get("Metadata", [])
    except httpx.HTTPError as exc:
        logger.warning("Plex-opslag fejlede (server utilgængelig?): %s", exc)
        return None

    match = _match_movie(results, tmdb_id, title, year)
    if match is None:
        return None
    return {"rating_key": match, "machine_identifier": machine_identifier}


def _match_movie(
    results: list[dict], tmdb_id: int | None, title: str | None, year: int | None
) -> str | None:
    """Pure matching logic, split out from find_movie so it's directly
    testable without mocking HTTP — mirrors tmdb_client._director(). Prefers
    an exact TMDb-id match via `Guid[].id` (format "tmdb://<id>" — only
    present for some Plex agent versions), falls back to exact title+year."""
    movies = [item for item in results if item.get("type") == "movie"]

    if tmdb_id is not None:
        for item in movies:
            guids = [g.get("id", "") for g in item.get("Guid", [])]
            if any(f"tmdb://{tmdb_id}" in g for g in guids):
                return str(item["ratingKey"])

    for item in movies:
        if item.get("title") == title and item.get("year") == year:
            return str(item["ratingKey"])

    return None


def build_play_url(rating_key: str, machine_identifier: str) -> str:
    return (
        f"{_base_url()}/web/index.html#!/server/{machine_identifier}"
        f"/details?key=%2Flibrary%2Fmetadata%2F{rating_key}"
    )
