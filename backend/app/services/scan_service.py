from app.integrations import discogs_client, tmdb_client, upc_client
from app.models.scan import MovieCandidate


def _alternate_upc_ean_form(barcode: str) -> str | None:
    """UPC-A (12 digits) and EAN-13 (13 digits) encode the same code when
    the EAN-13 form is just a leading zero prepended to the UPC-A form (see
    MOVIE_API_REFERENCE.md) — but a barcode-detection library or a lookup
    service's own database isn't always consistent about which length it
    reports/expects. Returns the other length, or None if `barcode` isn't a
    plain 12/13-digit UPC-A/EAN-13 code to begin with (BUGS.md #19)."""
    if len(barcode) == 13 and barcode.startswith("0") and barcode.isdigit():
        return barcode[1:]
    if len(barcode) == 12 and barcode.isdigit():
        return f"0{barcode}"
    return None


async def _lookup_title(barcode: str) -> str | None:
    guessed_title = await upc_client.lookup_title(barcode)
    if not guessed_title:
        # UPCitemdb's trial tier is US-retail-centric and often misses
        # European EAN-13 movie barcodes — Discogs' community-catalogued
        # database has better international DVD/Blu-ray coverage.
        guessed_title = await discogs_client.lookup_title(barcode)
    return guessed_title


async def lookup_by_barcode(barcode: str) -> dict:
    barcode = barcode.strip()
    guessed_title = await _lookup_title(barcode)

    if not guessed_title:
        alternate = _alternate_upc_ean_form(barcode)
        if alternate:
            guessed_title = await _lookup_title(alternate)

    if not guessed_title:
        return {"guessed_title": None, "candidates": []}

    # Searches both TMDb databases (feature #49) — a scanned barcode's
    # product could be either. Movies are listed first (the original,
    # still-primary use case), TV results after; each candidate carries its
    # own `media_kind` so the frontend can save to the right resource. See
    # BUGS.md #20: a real scanned barcode ("The Americans" boxset) turned
    # out to be a TV series, which the movie-only search could never match.
    raw_movie_candidates = await tmdb_client.search_movies(guessed_title)
    raw_tv_candidates = await tmdb_client.search_tv(guessed_title)
    candidates = [
        MovieCandidate(**candidate, media_kind="movie") for candidate in raw_movie_candidates
    ] + [MovieCandidate(**candidate, media_kind="tv") for candidate in raw_tv_candidates]
    return {"guessed_title": guessed_title, "candidates": candidates}
