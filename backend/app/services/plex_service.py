"""Plex-tilgængelighed for hele biblioteket (feature #88).

Erstatter feature #45's manuelle "Tjek Plex"-knap: i stedet for ét opslag
pr. film, når brugeren beder om det, henter og cacher vi hele Plex-bibliotekets
index og matcher vores egne film/serier mod det lokalt. Det er forskellen på
ét HTTP-kald pr. cache-periode og ét pr. filmkort på skærmen.

Matchning sker i faldende sikkerhed: TMDb-id (entydigt), derefter titel+år,
derefter titel alene *kun* når den er entydig i Plex. Hvert match bærer sin
egen `matched_by` med tilbage, så et falsk positivt badge kan spores til den
svageste af de tre regler i stedet for at være uforklarligt.
"""

import asyncio
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.integrations import plex_client
from app.integrations.plex_client import PlexFetchResult, PlexItem
from app.models.plex import (
    PlexAvailability,
    PlexAvailabilityMap,
    PlexDiagnostics,
    PlexSectionInfo,
    PlexUnmatchedItem,
)
from app.repositories import movie_repository, tv_show_repository

logger = logging.getLogger("moviedb")

# Hvor mange umatchede titler fejlsøgnings-endpointet viser. Nok til at få
# øje på et mønster ("alle mine nordiske titler mangler"), lidt nok til at
# svaret stadig kan læses på en telefon.
UNMATCHED_SAMPLE_SIZE = 25

# Engelske og danske bestemte/ubestemte artikler. Plex sorterer og gemmer
# ofte "The Matrix" som "Matrix, The" afhængigt af agent og sprogindstilling,
# og TMDb-titler kan have artiklen med hvor vores egen indtastning ikke har.
_LEADING_ARTICLES = ("the ", "a ", "an ", "den ", "det ", "de ", "en ", "et ")


@dataclass
class _Index:
    """Ét hentet Plex-bibliotek, forberedt til opslag."""

    result: PlexFetchResult
    fetched_at: float
    by_tmdb: dict[tuple[str, int], PlexItem] = field(default_factory=dict)
    by_title_year: dict[tuple[str, str, int], PlexItem] = field(default_factory=dict)
    # Titel -> alle elementer med den titel. Et opslag her bruges kun når
    # listen har præcis ét element; ellers ville "Batman" (1966/1989/2022)
    # give et vilkårligt af dem.
    by_title: dict[tuple[str, str], list[PlexItem]] = field(default_factory=dict)


_cache: _Index | None = None
# Uden låsen ville N samtidige biblioteks-kald (to faner, en PWA der
# genindlæser) hver især starte deres eget fulde Plex-hent, fordi de alle
# ser en tom/udløbet cache samtidig. Låsen gør at den første henter og
# resten venter på dens resultat.
_lock = asyncio.Lock()


def normalize_title(title: str | None) -> str:
    """Titel reduceret til det der reelt kan sammenlignes på tværs af TMDb,
    Plex og håndindtastning: uden accenter, tegnsætning, dobbelt-mellemrum
    og indledende artikel. "Amélie" og "Amelie", "The Matrix" og "Matrix"
    lander samme sted."""
    if not title:
        return ""
    text = unicodedata.normalize("NFKD", title)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9æøå ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for article in _LEADING_ARTICLES:
        if text.startswith(article):
            text = text[len(article):]
            break
    return text


def _build_index(result: PlexFetchResult) -> _Index:
    index = _Index(result=result, fetched_at=time.time())
    for item in result.items:
        if item.tmdb_id is not None:
            index.by_tmdb.setdefault((item.kind, item.tmdb_id), item)
        normalized = normalize_title(item.title)
        if not normalized:
            continue
        if item.year is not None:
            index.by_title_year.setdefault((item.kind, normalized, item.year), item)
        index.by_title.setdefault((item.kind, normalized), []).append(item)
    return index


def _match(index: _Index, kind: str, tmdb_id: int | None, title: str | None, year: int | None):
    """Returnerer (PlexItem, matched_by) eller (None, None)."""
    if tmdb_id is not None:
        item = index.by_tmdb.get((kind, tmdb_id))
        if item is not None:
            return item, "tmdb"

    normalized = normalize_title(title)
    if not normalized:
        return None, None

    if year is not None:
        # ±1 år: udgivelsesåret i Plex følger ofte den lokale udgivelse, mens
        # TMDb bruger premieren — en films årstal kan derfor lovligt afvige
        # med ét uden at det er en anden film.
        for candidate_year in (year, year - 1, year + 1):
            item = index.by_title_year.get((kind, normalized, candidate_year))
            if item is not None:
                return item, "title_year"

    candidates = index.by_title.get((kind, normalized), [])
    if len(candidates) == 1:
        return candidates[0], "title"

    return None, None


def _availability(index: _Index, kind: str, tmdb_id, title, year) -> PlexAvailability | None:
    item, matched_by = _match(index, kind, tmdb_id, title, year)
    if item is None:
        return None
    machine_identifier = index.result.machine_identifier
    return PlexAvailability(
        available=True,
        # Uden machineIdentifier kan der ikke bygges en gyldig web-URL. Badget
        # skal stadig vises (vi *ved* filmen er i Plex) — bare uden link.
        play_url=(
            plex_client.build_play_url(item.rating_key, machine_identifier)
            if machine_identifier
            else None
        ),
        matched_by=matched_by,
        plex_title=item.title,
        plex_year=item.year,
    )


async def _get_index(force_refresh: bool = False) -> _Index:
    """Cachet biblioteks-index. Ved fejl caches udfaldet også — ellers ville
    hver eneste sideindlæsning forsøge (og vente på timeout for) en Plex-
    server der er slukket."""
    global _cache

    async with _lock:
        ttl = max(settings.plex_cache_ttl_seconds, 0)
        if (
            not force_refresh
            and _cache is not None
            and ttl > 0
            and (time.time() - _cache.fetched_at) < ttl
        ):
            return _cache

        result = await plex_client.fetch_library()
        _cache = _build_index(result)
        return _cache


def invalidate_cache() -> None:
    global _cache
    _cache = None


def _fetched_at_iso(index: _Index) -> str:
    return datetime.fromtimestamp(index.fetched_at, tz=timezone.utc).isoformat()


async def get_availability_map(
    db: AsyncIOMotorDatabase, kind: str, force_refresh: bool = False
) -> PlexAvailabilityMap:
    """Hele bibliotekets Plex-status for én ressource-type ("movie"/"show")."""
    configured = plex_client.is_configured()
    if not configured:
        return PlexAvailabilityMap(
            configured=False,
            ok=False,
            error="Plex er ikke konfigureret — sæt server-URL og token under Indstillinger.",
            cache_ttl_seconds=settings.plex_cache_ttl_seconds,
        )

    index = await _get_index(force_refresh=force_refresh)
    if not index.result.ok:
        return PlexAvailabilityMap(
            configured=True,
            ok=False,
            error=index.result.error,
            fetched_at=_fetched_at_iso(index),
            cache_ttl_seconds=settings.plex_cache_ttl_seconds,
        )

    items: dict[str, PlexAvailability] = {}
    for doc in await _library_docs(db, kind):
        availability = _availability(
            index, kind, doc.get("tmdb_id"), _doc_title(doc, kind), doc.get("year")
        )
        if availability is not None:
            items[str(doc["_id"])] = availability

    return PlexAvailabilityMap(
        configured=True,
        ok=True,
        fetched_at=_fetched_at_iso(index),
        cache_ttl_seconds=settings.plex_cache_ttl_seconds,
        items=items,
    )


def _doc_title(doc: dict, kind: str) -> str | None:
    # Film hedder `title`, TV-serier hedder `name` — de to collections deler
    # bevidst ikke datamodel (CLAUDE.md), så feltnavnet skal vælges her.
    return doc.get("title") if kind == "movie" else doc.get("name")


async def _library_docs(db: AsyncIOMotorDatabase, kind: str) -> list[dict]:
    if kind == "movie":
        return await movie_repository.find_all_for_plex_match(db)
    return await tv_show_repository.find_all_for_plex_match(db)


async def get_diagnostics(db: AsyncIOMotorDatabase, force_refresh: bool = True) -> PlexDiagnostics:
    """Feature #88's fejlsøgning. Kører som standard med et friskt hent, så
    en admin der lige har rettet URL eller token ser den nye virkelighed og
    ikke et cachet svar fra før rettelsen."""
    started = time.perf_counter()
    configured = plex_client.is_configured()

    base = PlexDiagnostics(
        configured=configured,
        server_url=settings.plex_server_url,
        token_configured=bool(settings.plex_token),
        ok=False,
        cache_ttl_seconds=settings.plex_cache_ttl_seconds,
    )

    if not configured:
        missing = []
        if not settings.plex_server_url:
            missing.append("server-URL")
        if not settings.plex_token:
            missing.append("token")
        base.error = f"Plex er ikke konfigureret (mangler {' og '.join(missing)})"
        base.duration_ms = int((time.perf_counter() - started) * 1000)
        return base

    index = await _get_index(force_refresh=force_refresh)
    result = index.result

    base.server_name = result.server_name
    base.server_version = result.server_version
    base.machine_identifier = result.machine_identifier
    base.fetched_at = _fetched_at_iso(index)
    base.cache_age_seconds = int(time.time() - index.fetched_at)
    base.sections = [
        PlexSectionInfo(
            key=section.key,
            title=section.title,
            type=section.type,
            item_count=section.item_count,
            with_tmdb_guid=section.with_tmdb_guid,
            with_imdb_guid=section.with_imdb_guid,
        )
        for section in result.sections
    ]
    base.plex_movie_count = sum(1 for item in result.items if item.kind == "movie")
    base.plex_show_count = sum(1 for item in result.items if item.kind == "show")

    if not result.ok:
        base.error = result.error
        base.duration_ms = int((time.perf_counter() - started) * 1000)
        logger.warning("Plex-diagnostik: %s", result.error)
        return base

    base.ok = True

    for kind in ("movie", "show"):
        docs = await _library_docs(db, kind)
        matched = 0
        unmatched: list[PlexUnmatchedItem] = []
        for doc in docs:
            title = _doc_title(doc, kind)
            item, matched_by = _match(index, kind, doc.get("tmdb_id"), title, doc.get("year"))
            if item is None:
                if len(unmatched) < UNMATCHED_SAMPLE_SIZE:
                    unmatched.append(
                        PlexUnmatchedItem(
                            title=title or "(uden titel)",
                            year=doc.get("year"),
                            tmdb_id=doc.get("tmdb_id"),
                        )
                    )
                continue
            matched += 1
            if matched_by == "tmdb":
                base.matched_by_tmdb += 1
            else:
                base.matched_by_title += 1

        if kind == "movie":
            base.library_movie_count = len(docs)
            base.matched_movies = matched
            base.unmatched_movies = unmatched
        else:
            base.library_show_count = len(docs)
            base.matched_shows = matched
            base.unmatched_shows = unmatched

    base.duration_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "Plex-diagnostik: %s/%s film og %s/%s serier matchet (%s via TMDb-id, %s via titel)",
        base.matched_movies,
        base.library_movie_count,
        base.matched_shows,
        base.library_show_count,
        base.matched_by_tmdb,
        base.matched_by_title,
    )
    return base
