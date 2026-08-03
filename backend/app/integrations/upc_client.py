import logging

import httpx

from app.integrations.text_cleanup import clean_bracketed_title

BASE_URL = "https://api.upcitemdb.com/prod/trial/lookup"

logger = logging.getLogger("moviedb")


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
        logger.info("UPCitemdb: intet match for %s", barcode)
        return None

    raw_title = items[0].get("title")
    if not raw_title:
        logger.info("UPCitemdb: match uden titel-felt for %s", barcode)
        return None

    title = clean_bracketed_title(raw_title)
    logger.info("UPCitemdb: %s -> %r", barcode, title)
    return title
