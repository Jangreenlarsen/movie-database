import logging

import httpx

from app.core.config import settings
from app.integrations.http_json import parse_json
from app.integrations.text_cleanup import clean_bracketed_title

BASE_URL = "https://api.ean-search.org/api"

logger = logging.getLogger("moviedb")


async def lookup_title(barcode: str) -> str | None:
    """Fourth and last UPC/EAN -> title fallback, tried after UPCitemdb,
    Discogs and UPCDatabase.org all miss (feature #76, added 2026-08-03 —
    Jan's own paid account, bought specifically in hope of better Nordic/
    Danish coverage than the three free sources). Free tier doesn't exist
    here (it's a paid-from-the-start service), so — unlike the other three
    — an unset key isn't a normal/expected state, but the same "skip
    entirely rather than call an API we know will reject us" principle
    still applies. Never raises: nice-to-have prefill, not a critical
    path (see MOVIE_API_REFERENCE.md)."""
    if not settings.ean_search_api_key:
        logger.info("EAN-Search.org: intet token konfigureret, springer opslag over for %s", barcode)
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                BASE_URL,
                params={
                    "token": settings.ean_search_api_key,
                    "op": "barcode-lookup",
                    "format": "json",
                    "ean": barcode,
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("EAN-Search.org lookup failed for %s: %s", barcode, exc)
        return None

    if response.status_code != 200:
        logger.info("EAN-Search.org lookup returned %s for %s", response.status_code, barcode)
        return None

    data = parse_json(response)
    if data is None:
        logger.warning("EAN-Search.org: svar var ikke gyldig JSON for %s", barcode)
        return None
    if not isinstance(data, list) or not data:
        logger.info("EAN-Search.org: intet match for %s", barcode)
        return None

    first = data[0]
    if "error" in first:
        # Samme "skelnen mellem afvist token og ægte tomhed"-princip som
        # upcdatabase_client (BUGS.md #37) — en fejl her ("Invalid token",
        # utilstrækkelig saldo osv.) er noget helt andet end et ægte miss.
        logger.warning("EAN-Search.org afviste opslaget for %s: %s", barcode, first["error"])
        return None

    raw_title = first.get("name")
    if not raw_title:
        logger.info("EAN-Search.org: match uden navn-felt for %s", barcode)
        return None

    title = clean_bracketed_title(raw_title)
    logger.info("EAN-Search.org: %s -> %r", barcode, title)
    return title


# Michael Jackson - Thriller — et rigtigt, stabilt EAN fra EAN-Search.orgs
# egen API-dokumentation, kun brugt til at bekræfte at token'et accepteres.
_TEST_BARCODE = "5099750442227"


async def test_connection() -> tuple[bool, str]:
    if not settings.ean_search_api_key:
        return False, "Intet token sat"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                BASE_URL,
                params={
                    "token": settings.ean_search_api_key,
                    "op": "barcode-lookup",
                    "format": "json",
                    "ean": _TEST_BARCODE,
                },
            )
    except httpx.HTTPError as exc:
        return False, f"Netværksfejl: {exc}"

    if response.status_code != 200:
        return False, f"Uventet svar (HTTP {response.status_code})"

    data = parse_json(response)
    if not isinstance(data, list):
        # BUGS.md #105 — uden dette svarede "Test forbindelse" "Virker" på
        # en HTML-side.
        return False, "Ugyldigt svar fra EAN-Search.org (ikke JSON)"
    if data and isinstance(data[0], dict) and "error" in data[0]:
        return False, f"Token afvist: {data[0]['error']}"
    return True, "Virker"
