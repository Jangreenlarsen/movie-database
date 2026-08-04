import logging

from app.core.config import settings
from app.integrations import (
    discogs_client,
    ean_search_client,
    tmdb_client,
    upc_client,
    upcdatabase_client,
)
from app.models.scan import MovieCandidate

logger = logging.getLogger("moviedb")

# Feature #77 — de fire kilder i deres normale (standard-primær) rækkefølge.
# Modul-referencer, ikke funktions-referencer — så .lookup_title slås op
# friskt ved hvert kald, og fx test-monkeypatching af en klients funktion
# efter modulets indlæsning stadig respekteres (samme fejlklasse som
# system_settings_service._TEST_CONNECTION_CLIENTS allerede undgår).
# `_ordered_sources` trækker den admin-valgte primære kilde forrest; resten
# følger stadig denne rækkefølge som fallback.
BARCODE_SOURCES = (
    ("upcitemdb", upc_client),
    ("discogs", discogs_client),
    ("upcdatabase", upcdatabase_client),
    ("ean_search", ean_search_client),
)


def _ordered_sources():
    primary = settings.primary_barcode_source
    return sorted(BARCODE_SOURCES, key=lambda item: item[0] != primary)


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


async def _lookup_title(barcode: str) -> tuple[str | None, str | None]:
    """Tries each source in the admin's configured order (feature #77),
    stopping at the first match. Returns (title, source_name) — source_name
    is None alongside a None title, and is one of BARCODE_SOURCES' keys
    otherwise, used to record which source resolved this barcode (#77's
    Statistics breakdown)."""
    for name, client in _ordered_sources():
        title = await client.lookup_title(barcode)
        if title:
            return title, name
    return None, None


# Found 2026-08-04 via production logs: 3 of 4 real scans that day found a
# genuine title-guess (barcode resolution itself was working perfectly) but
# still surfaced *nothing*, because TMDb's search is a literal keyword
# match and a UPC/EAN source's title noise — distributor/label prefixes
# ("Simply HE The Americans" — real production example) — makes the *full*
# guessed title match zero candidates even though the real title is right
# there in it. Retrying with the leftmost word progressively dropped is
# cheap (TMDb has no meaningful rate limit here) and safe: it only ever
# *removes* words from the front, so it can't turn one real title into an
# unrelated one — it can only reveal a title that was already present.
# Capped at 3 dropped words — real noise prefixes are short ("Simply HE",
# not five words long); a title needing more than that is more likely a
# genuine miss than fixable noise.
_MAX_LEADING_WORDS_TO_DROP = 3


async def _search_tmdb_with_fallback(guessed_title: str) -> tuple[list[dict], list[dict], str]:
    words = guessed_title.split()
    for start in range(min(len(words), _MAX_LEADING_WORDS_TO_DROP + 1)):
        query = " ".join(words[start:])
        if not query:
            break
        movies = await tmdb_client.search_movies(query)
        tv = await tmdb_client.search_tv(query)
        if movies or tv:
            return movies, tv, query
    return [], [], guessed_title


async def lookup_by_barcode(barcode: str) -> dict:
    barcode = barcode.strip()
    guessed_title, barcode_source = await _lookup_title(barcode)

    if not guessed_title:
        alternate = _alternate_upc_ean_form(barcode)
        if alternate:
            guessed_title, barcode_source = await _lookup_title(alternate)

    if not guessed_title:
        # BUGS.md #34 — this WARNING is the one clear line to grep for when
        # diagnosing "scan finder ingen film": it means all four sources
        # (UPCitemdb, Discogs, UPCDatabase.org, EAN-Search.org — see the
        # INFO/WARNING line each one already logged for its own miss/reject)
        # came back empty, not that the request itself failed.
        logger.warning(
            "Intet titel-gæt fundet for stregkode %s (forsøgt mod UPCitemdb, Discogs, "
            "UPCDatabase.org, EAN-Search.org, inkl. alternativ UPC/EAN-form)",
            barcode,
        )
        return {"guessed_title": None, "barcode_source": None, "candidates": []}

    # Searches both TMDb databases (feature #49) — a scanned barcode's
    # product could be either. Movies are listed first (the original,
    # still-primary use case), TV results after; each candidate carries its
    # own `media_kind` so the frontend can save to the right resource. See
    # BUGS.md #20: a real scanned barcode ("The Americans" boxset) turned
    # out to be a TV series, which the movie-only search could never match.
    raw_movie_candidates, raw_tv_candidates, matched_query = await _search_tmdb_with_fallback(
        guessed_title
    )
    candidates = [
        MovieCandidate(**candidate, media_kind="movie") for candidate in raw_movie_candidates
    ] + [MovieCandidate(**candidate, media_kind="tv") for candidate in raw_tv_candidates]
    if candidates and matched_query != guessed_title:
        logger.info(
            "Titel-gæt '%s' (stregkode %s) gav ingen TMDb-kandidater, men et afkortet "
            "forsøg '%s' gjorde",
            guessed_title,
            barcode,
            matched_query,
        )
    if not candidates:
        logger.info(
            "Stregkode %s gav titel-gæt '%s', men ingen TMDb-kandidater (hverken film eller TV, "
            "heller ikke efter at have prøvet uden op til %s indledende ord)",
            barcode,
            guessed_title,
            _MAX_LEADING_WORDS_TO_DROP,
        )
    return {
        "guessed_title": guessed_title,
        "barcode_source": barcode_source,
        "candidates": candidates,
    }
