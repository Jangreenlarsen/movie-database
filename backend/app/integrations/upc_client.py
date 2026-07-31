import logging
import re

import httpx

BASE_URL = "https://api.upcitemdb.com/prod/trial/lookup"

_BRACKETED_SUFFIX = re.compile(r"[\[(][^\])]*[\])]")

logger = logging.getLogger("moviedb")


def _clean_title(raw_title: str) -> str:
    cleaned = _BRACKETED_SUFFIX.sub(" ", raw_title)
    return " ".join(cleaned.split()).strip()


async def lookup_title(barcode: str) -> str | None:
    """Best-effort UPC -> title guess. Never raises: this is a nice-to-have
    prefill, not a critical path (see MOVIE_API_REFERENCE.md)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(BASE_URL, params={"upc": barcode})
    except httpx.HTTPError as exc:
        logger.warning("UPC lookup failed for %s: %s", barcode, exc)
        return None

    if response.status_code != 200:
        logger.info("UPC lookup returned %s for %s", response.status_code, barcode)
        return None

    items = response.json().get("items") or []
    if not items:
        return None

    raw_title = items[0].get("title")
    if not raw_title:
        return None

    return _clean_title(raw_title)
