import logging

import httpx

from app.core.config import settings
from app.integrations.text_cleanup import clean_bracketed_title

BASE_URL = "https://api.upcdatabase.org/product"

logger = logging.getLogger("moviedb")


async def lookup_title(barcode: str) -> str | None:
    """Third UPC/EAN -> title fallback, tried after UPCitemdb and Discogs
    both miss (added 2026-08-03 in an attempt to improve coverage for
    Nordic/Danish DVD/Blu-ray releases, which neither of the other two
    typically catalogue — see MOVIE_API_REFERENCE.md). Free tier only
    (100 lookups/day), so this is skipped entirely — not even attempted —
    when no token is configured, same "don't call an API we know will
    reject us" principle as `tmdb_client._require_token`. Never raises:
    nice-to-have prefill, not a critical path."""
    if not settings.upcdatabase_token:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{BASE_URL}/{barcode}",
                headers={"Authorization": f"Bearer {settings.upcdatabase_token}"},
            )
    except httpx.HTTPError as exc:
        logger.warning("UPCDatabase.org lookup failed for %s: %s", barcode, exc)
        return None

    if response.status_code != 200:
        logger.info("UPCDatabase.org lookup returned %s for %s", response.status_code, barcode)
        return None

    data = response.json()
    if not data.get("success"):
        return None

    raw_title = data.get("title")
    if not raw_title:
        return None

    return clean_bracketed_title(raw_title)
