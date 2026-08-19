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
from app.core.errors import TmdbNotFoundError, TmdbRateLimitedError, TmdbUnavailableError
from app.db import get_database
from app.integrations import plex_client, tmdb_client
from app.integrations.plex_client import PlexFetchResult, PlexItem
from app.models.movie import MediaType, MovieCreate, MovieFormat
from app.models.plex import (
    PlexAvailability,
    PlexAvailabilityMap,
    PlexClientInfo,
    PlexClientList,
    PlexDiagnostics,
    PlexImportItem,
    PlexImportRequest,
    PlexImportResult,
    PlexPlayResult,
    PlexSectionInfo,
    PlexUnmatchedItem,
)
from app.models.tv_show import TvShowCreate
from app.repositories import movie_repository, system_settings_repository, tv_show_repository
from app.services import audit_log_service, movie_service, tv_show_service

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
    db: AsyncIOMotorDatabase,
    kind: str,
    force_refresh: bool = False,
    plex_play_enabled: bool = True,
) -> PlexAvailabilityMap:
    """Hele bibliotekets Plex-status for én ressource-type ("movie"/"show").

    Feature #178-opfølgning (Jan: "sæt op i users styring hvem kan se og
    bruge vis iplex/spil i plex i detajle for film/tv") — `plex_play_enabled`
    er DENNE brugers egen tilladelse (fra `current_user["plex_play_enabled"]`
    i API-laget). Håndhævet her, ikke kun skjult i UI'et (CLAUDE.md regel
    16): er den `False`, udelades `play_url` fra ethvert element i svaret,
    så den reelle Plex-URL aldrig sendes til en klient uden adgang, uanset om
    browserens devtools/netværksfane bruges til at omgå en skjult knap.
    `available`/`matched_by`/badge-visning er uændret — kun selve
    afspilnings-linket er omfattet, jf. Jans afgrænsning."""
    # Feature #178 — kun en boolean; se PlexAvailabilityMap.shield_configured
    # for hvorfor den følger med her i stedet for et separat admin-only kald.
    shield_configured = bool(settings.plex_shield_client_identifier)

    configured = plex_client.is_configured()
    if not configured:
        return PlexAvailabilityMap(
            configured=False,
            ok=False,
            error="Plex er ikke konfigureret — sæt server-URL og token under Indstillinger.",
            cache_ttl_seconds=settings.plex_cache_ttl_seconds,
            shield_configured=shield_configured,
            play_allowed=plex_play_enabled,
        )

    index = await _get_index(force_refresh=force_refresh)
    if not index.result.ok:
        return PlexAvailabilityMap(
            configured=True,
            ok=False,
            error=index.result.error,
            fetched_at=_fetched_at_iso(index),
            cache_ttl_seconds=settings.plex_cache_ttl_seconds,
            shield_configured=shield_configured,
            play_allowed=plex_play_enabled,
        )

    items: dict[str, PlexAvailability] = {}
    for doc in await _library_docs(db, kind):
        availability = _availability(
            index, kind, doc.get("tmdb_id"), _doc_title(doc, kind), doc.get("year")
        )
        if availability is not None:
            if not plex_play_enabled:
                availability = availability.model_copy(update={"play_url": None})
            items[str(doc["_id"])] = availability

    return PlexAvailabilityMap(
        configured=True,
        ok=True,
        fetched_at=_fetched_at_iso(index),
        cache_ttl_seconds=settings.plex_cache_ttl_seconds,
        shield_configured=shield_configured,
        play_allowed=plex_play_enabled,
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


async def _find_doc(db: AsyncIOMotorDatabase, kind: str, item_id: str) -> dict | None:
    if kind == "movie":
        return await movie_repository.find_by_id(db, item_id)
    return await tv_show_repository.find_by_id(db, item_id)


async def list_clients() -> PlexClientList:
    """Feature #178 — admin-opsætningens "Hent tilgængelige klienter", til
    at finde Shield TV'ets client-id én gang (se
    `plex_client.fetch_clients`'s docstring for hvorfor det ikke slås op ved
    hver afspilning). BUGS.md #76 — `raw_entry_count` føres videre uændret,
    se `PlexClientList`'s note for hvorfor det er der."""
    clients, raw_count, error = await plex_client.fetch_clients()
    return PlexClientList(
        ok=error is None,
        error=error,
        items=[
            PlexClientInfo(name=c.name, machine_identifier=c.machine_identifier, product=c.product)
            for c in clients
        ],
        raw_entry_count=raw_count,
    )


async def _resolve_for_shield(
    db: AsyncIOMotorDatabase, kind: str, item_id: str
) -> tuple[str, str] | PlexPlayResult:
    """Fælles opslag for `play_on_shield`/`show_on_shield`: bekræfter Shield
    er konfigureret, dokumentet findes, og det kan matches i Plex. Genbruger
    det samme matchnings-index som badge/afspil-link (feature #88) — den
    samme regel for hvilket Plex-element der hører til vores film/serie skal
    gælde alle tre veje, ellers kunne "ligger i Plex" og "kan afspilles/vises
    på Shield" komme til at være uenige om samme titel. Returnerer enten
    `(rating_key, machine_identifier)` eller et færdigt fejlsvar."""
    if not settings.plex_shield_client_identifier:
        return PlexPlayResult(
            ok=False,
            message="Shield TV er ikke konfigureret endnu — sæt dens klient-id under Indstillinger.",
        )

    doc = await _find_doc(db, kind, item_id)
    if doc is None:
        return PlexPlayResult(ok=False, message="Ikke fundet.")

    index = await _get_index()
    if not index.result.ok:
        return PlexPlayResult(
            ok=False, message=index.result.error or "Plex-biblioteket kunne ikke hentes."
        )

    machine_identifier = index.result.machine_identifier
    if not machine_identifier:
        return PlexPlayResult(ok=False, message="Plex-serverens id kunne ikke bestemmes.")

    item, _matched_by = _match(index, kind, doc.get("tmdb_id"), _doc_title(doc, kind), doc.get("year"))
    if item is None:
        return PlexPlayResult(ok=False, message="Findes ikke i Plex.")

    return item.rating_key, machine_identifier


async def play_on_shield(db: AsyncIOMotorDatabase, kind: str, item_id: str) -> PlexPlayResult:
    """Feature #178 (Jan: "når man trykker på vis i plex så er option at
    starte den i plex på shield der også"). Direkte `playMedia` (`plex_client.
    play_on_client`) — bekræftet fungerende på Jans udstyr, sender
    `directPlay=1`/`directStream=1` for at bede PMS forsøge direkte
    afspilning. Se `show_on_shield` for den alternative, valgfri
    `mirror/details`-vej (kun til test, se dens docstring)."""
    resolved = await _resolve_for_shield(db, kind, item_id)
    if isinstance(resolved, PlexPlayResult):
        return resolved
    rating_key, machine_identifier = resolved

    ok, message = await plex_client.play_on_client(
        rating_key=rating_key,
        server_machine_identifier=machine_identifier,
        client_identifier=settings.plex_shield_client_identifier,
    )
    return PlexPlayResult(ok=ok, message=message)


async def show_on_shield(db: AsyncIOMotorDatabase, kind: str, item_id: str) -> PlexPlayResult:
    """2026-08-19 (Jan, efter research bekræftede hvorfor `mirror/details`
    ikke virkede: "lave igen en knap mere til 'vis i plex' sådan vi kan
    teste på den funktion igen ... jeg se på om der skulle være
    opdateringer til plex klient") — genindfører `mirror/details`
    (`plex_client.navigate_client_to_media`) som en SEPARAT, valgfri
    test-knap ved siden af `play_on_shield`, ikke en erstatning for den.
    Se `navigate_client_to_media`s docstring for hele baggrunden."""
    resolved = await _resolve_for_shield(db, kind, item_id)
    if isinstance(resolved, PlexPlayResult):
        return resolved
    rating_key, machine_identifier = resolved

    ok, message = await plex_client.navigate_client_to_media(
        rating_key=rating_key,
        server_machine_identifier=machine_identifier,
        client_identifier=settings.plex_shield_client_identifier,
    )
    return PlexPlayResult(ok=ok, message=message)


async def stop_shield() -> PlexPlayResult:
    """Opfølgning på feature #178 (Jan: "Afspil på Shield TV" skal være en
    rigtig start/stop-toggle, ikke kun starte). Stopper hvad end Shielden
    lige nu afspiller — intet match-opslag nødvendigt (i modsætning til
    `play_on_shield`), da en stop-kommando ikke refererer til nogen titel."""
    if not settings.plex_shield_client_identifier:
        return PlexPlayResult(
            ok=False,
            message="Shield TV er ikke konfigureret endnu — sæt dens klient-id under Indstillinger.",
        )

    ok, message = await plex_client.stop_client(settings.plex_shield_client_identifier)
    return PlexPlayResult(ok=ok, message=message)


def _library_as_index(docs: list[dict], kind: str) -> _Index:
    """Vores eget bibliotek pakket i *samme* index-form som Plex-indexet
    (feature #90).

    Formålet er at kunne stille det omvendte spørgsmål — "har vi allerede
    denne Plex-film?" — gennem præcis den samme `_match`, som feature #88
    bruger til "ligger vores film i Plex?". To separate implementeringer
    ville uundgåeligt drive fra hinanden, og så ville badget og importen
    kunne være uenige om hvad der er samme film. `PlexItem` genbruges som
    ren container; `rating_key` bærer her vores eget dokument-id."""
    items = [
        PlexItem(
            kind=kind,
            rating_key=str(doc["_id"]),
            title=_doc_title(doc, kind) or "",
            year=doc.get("year"),
            tmdb_id=doc.get("tmdb_id"),
            imdb_id=None,
        )
        for doc in docs
    ]
    return _build_index(PlexFetchResult(ok=True, items=items))


async def _resolve_tmdb_id(kind: str, title: str, year: int | None) -> int | None:
    """TMDb-id for et Plex-element der ikke selv havde et (ældre agenter).

    Kun et entydigt match tæller: præcis ét søgeresultat med samme
    normaliserede titel *og* samme årstal. Jans valg 2026-08-08 — hellere
    rapportere titlen som umatchet end lade et gæt blive til data der ser
    lige så rigtig ud som resten af biblioteket."""
    if not title:
        return None

    search = tmdb_client.search_movies if kind == "movie" else tmdb_client.search_tv
    candidates = await search(title)

    normalized = normalize_title(title)
    matches = [
        candidate
        for candidate in candidates
        if normalize_title(candidate.get("title")) == normalized
        and candidate.get("year") is not None
        and candidate["year"] == year
    ]
    return matches[0]["tmdb_id"] if len(matches) == 1 else None


# BUGS.md #52 — formatet når Plex ikke kan oplyse en opløsning. Ikke et gæt
# på må og få: samme fallback som `movie_repository._FORMAT_LABEL_MIGRATIONS`
# bruger for gamle "Digital"-poster uden kvalitetstrin, og HD er langt den
# almindeligste. Alternativet — at springe elementet over — betød at en hel
# kategori (typisk TV-serier, hvor opløsningen kræver et ekstra kald pr.
# serie) stiltiende aldrig blev importeret.
FALLBACK_DIGITAL_FORMAT = MovieFormat.DIGITAL_HD


def format_for_resolution(resolution: str | None) -> MovieFormat | None:
    """Plex' `videoResolution` oversat til appens eget format-vokabular
    (feature #91).

    Værdierne findes allerede i `MovieFormat` fra v0.22.0, hvor "digital"
    blev delt i kvalitetstrin — så en importeret film står med præcis samme
    format som en håndoprettet, ikke et parallelt sæt Plex-etiketter.

    Plex normaliserer typisk 2160p til strengen "4k", men ikke altid, og
    ældre servere kan sende det rå tal. Begge former håndteres."""
    if not resolution:
        return None

    value = resolution.strip().lower()
    if value in ("4k", "2160", "2160p"):
        return MovieFormat.DIGITAL_UHD
    if value == "sd":
        return MovieFormat.DIGITAL_STD

    digits = re.match(r"(\d+)", value)
    if digits is None:
        # Ukendt streng — hellere lade formatet stå tomt end gætte forkert.
        return None
    height = int(digits.group(1))
    if height >= 2160:
        return MovieFormat.DIGITAL_UHD  # D-4K
    if height >= 1080:
        return MovieFormat.DIGITAL_HD  # D-1080
    # v0.105.0 — 720 fik sit eget trin (D-720); alt derunder (576/480) er SD.
    if height >= 720:
        return MovieFormat.DIGITAL_720
    return MovieFormat.DIGITAL_STD


async def _create_imported(
    db: AsyncIOMotorDatabase, item: PlexItem, tmdb_id: int, tags: list[str], registered_by: str
) -> MovieFormat | None:
    """Opretter ét importeret element og returnerer det format der blev sat,
    så resultatet kan rapporteres tilbage. Alt fra Plex får `media_type:
    Digital` — det ligger per definition på en medieserver, ikke på en
    hylde."""
    if item.kind == "movie":
        movie_format = format_for_resolution(item.resolution) or FALLBACK_DIGITAL_FORMAT
        await movie_service.create_movie(
            db,
            MovieCreate(
                tmdb_id=tmdb_id,
                tags=tags,
                media_type=MediaType.DIGITAL,
                format=movie_format,
            ),
            registered_by,
        )
        return movie_format

    # Sæsoner *og* opløsning i ét kald: en serie har ingen opløsning i sig
    # selv, den ligger på episoderne. Uden sæsonerne ville en importeret
    # serie desuden lande med alt markeret "ikke ejet" selvom den står på
    # serveren.
    details = await plex_client.fetch_show_details(item.rating_key)
    show_format = format_for_resolution(details.resolution) or FALLBACK_DIGITAL_FORMAT
    await tv_show_service.create_tv_show(
        db,
        TvShowCreate(
            tmdb_id=tmdb_id,
            tags=tags,
            owned_seasons=details.seasons,
            media_type=MediaType.DIGITAL,
            format=show_format,
        ),
        registered_by,
    )
    return show_format


async def import_from_plex(
    db: AsyncIOMotorDatabase, request: PlexImportRequest, registered_by: str
) -> PlexImportResult:
    """Opretter alt det Plex har, som portalen ikke har i forvejen.

    Batch-forudsætningerne tjekkes *før* løkken (CLAUDE.md regel 16): både
    en manglende Plex-konfiguration og et manglende TMDb-token ville få hvert
    eneste element til at fejle af samme grund, hvilket er en oplysning man
    skal have én gang — ikke hundrede.

    `dry_run` deler kode med den rigtige import med vilje. Havde
    forhåndsvisningen sin egen gennemgang, kunne de to nå at være uenige om
    hvad der ville ske."""
    if not plex_client.is_configured():
        return PlexImportResult(
            dry_run=request.dry_run,
            ok=False,
            error="Plex er ikke konfigureret — sæt server-URL og token under Indstillinger.",
        )

    if not settings.tmdb_api_token:
        return PlexImportResult(
            dry_run=request.dry_run,
            ok=False,
            error=(
                "Ingen TMDb-token sat — importen henter al metadata fra TMDb og kan "
                "ikke oprette noget uden."
            ),
        )

    index = await _get_index(force_refresh=request.dry_run)
    if not index.result.ok:
        return PlexImportResult(dry_run=request.dry_run, ok=False, error=index.result.error)

    result = PlexImportResult(dry_run=request.dry_run, ok=True)
    tags = [request.tag.strip()] if request.tag.strip() else []

    kinds = []
    if request.include_movies:
        kinds.append("movie")
    if request.include_shows:
        kinds.append("show")

    for kind in kinds:
        library_index = _library_as_index(await _library_docs(db, kind), kind)

        for item in [entry for entry in index.result.items if entry.kind == kind]:
            existing, _ = _match(library_index, kind, item.tmdb_id, item.title, item.year)
            if existing is not None:
                result.already_present += 1
                continue

            tmdb_id = item.tmdb_id
            resolved_via = "plex_guid"
            if tmdb_id is None:
                try:
                    tmdb_id = await _resolve_tmdb_id(kind, item.title, item.year)
                except TmdbRateLimitedError:
                    result.stopped_early = True
                    break
                except TmdbUnavailableError as exc:
                    # 429 kommer ad denne vej fra search_movies/search_tv
                    # (se tmdb_client), så rate-limit skal genkendes her også
                    # frem for at blive talt som en almindelig fejl.
                    if "rate-limit" in str(exc).lower():
                        result.stopped_early = True
                        break
                    result.failed.append(
                        PlexImportItem(kind=kind, title=item.title, year=item.year, reason=str(exc))
                    )
                    continue
                resolved_via = "tmdb_search"

            if tmdb_id is None:
                result.unmatched.append(
                    PlexImportItem(
                        kind=kind,
                        title=item.title,
                        year=item.year,
                        reason="Intet entydigt TMDb-match på titel og år",
                    )
                )
                continue

            entry = PlexImportItem(
                kind=kind,
                title=item.title,
                year=item.year,
                tmdb_id=tmdb_id,
                resolved_via=resolved_via,
                # Film bærer deres opløsning med fra sektions-listen, så
                # formatet kan vises allerede i forhåndsvisningen. En serie
                # har den kun på sine episoder, og at hente den for hver
                # eneste serie ville gøre en "hvad ville der ske?"-visning
                # lige så dyr som importen selv.
                format=format_for_resolution(item.resolution),
            )

            # BUGS.md #52 — kan Plex ikke oplyse opløsningen, importeres
            # elementet alligevel med fallback-formatet og markeres som
            # sådan. Før blev det sprunget over, hvilket betød at en hel
            # kategori stiltiende aldrig nåede ind i portalen.
            if entry.format is None:
                entry.format = FALLBACK_DIGITAL_FORMAT
                entry.format_is_fallback = True

            if request.dry_run:
                result.imported.append(entry)
                continue

            try:
                entry.format = await _create_imported(db, item, tmdb_id, tags, registered_by)
            except TmdbRateLimitedError:
                result.stopped_early = True
                break
            except (TmdbNotFoundError, TmdbUnavailableError) as exc:
                entry.reason = str(exc)
                result.failed.append(entry)
                continue
            result.imported.append(entry)

        if result.stopped_early:
            break

    logger.info(
        "Plex-import (%s): %s oprettet, %s fandtes i forvejen, %s umatchede, %s fejlede%s",
        "forhåndsvisning" if request.dry_run else "udført",
        len(result.imported),
        result.already_present,
        len(result.unmatched),
        len(result.failed),
        " (afbrudt af rate-limit)" if result.stopped_early else "",
    )

    # Jan: "søger for at tag på importerede i auto-scan plex er det tag som
    # er difineret under 'importer fra plex'". En rigtig (ikke dry-run) import
    # udført af en admin — ikke auto-scan-loopet selv, se `_AUTO_IMPORT_ACTOR`
    # nedenfor — opdaterer den delte definition, så det næste auto-scan
    # bruger samme tag uden at admin skal indstille det to steder.
    if not request.dry_run and registered_by != _AUTO_IMPORT_ACTOR:
        await system_settings_repository.apply_plex_auto_import_update(
            db, {"plex_import_tag": request.tag}
        )
        settings.plex_import_tag = request.tag

    return result


# Feature #181 (Jan: "jeg tro tilgengæld at vi skal have en automatisk scan
# af plex media server for ny film og tv serie, i dag er det en manual
# funktion"). Syntetisk aktør-navn til automatisk-oprettede poster og
# audit-log-entries — samme "gemmes kun som ren tekst, ingen FK"-princip som
# `registered_by`/`owner` allerede bruger (se models/backup.py's note).
_AUTO_IMPORT_ACTOR = "plex-auto-sync"


async def _run_one_auto_import_cycle(db: AsyncIOMotorDatabase) -> None:
    """Selve arbejdet for ÉN scan — udtrukket fra `run_auto_import_loop`
    nedenfor, så det kan testes isoleret uden `asyncio.sleep`/den uendelige
    løkke. Antager kaldstedet allerede har tjekket
    `settings.plex_auto_import_enabled`.

    Fejl her må ALDRIG vælte hele appen — samme best-effort-filosofi som
    resten af Plex-integrationen (se modulets docstring): fanges bredt og
    logges, uden at kaste videre."""
    try:
        result = await import_from_plex(
            db,
            PlexImportRequest(
                dry_run=False,
                include_movies=True,
                include_shows=True,
                tag=settings.plex_import_tag,
            ),
            _AUTO_IMPORT_ACTOR,
        )
    except Exception:
        logger.exception("Plex auto-import: uventet fejl under baggrunds-scan")
        return

    if not result.ok:
        logger.warning("Plex auto-import: scan fejlede (%s)", result.error)
        return

    # Kun logget når der reelt skete noget — ellers ville audit-loggen
    # druknes i "0 oprettet"-entries ved hver eneste interval, hele tiden.
    if result.imported:
        await audit_log_service.record(
            db,
            _AUTO_IMPORT_ACTOR,
            "plex.imported",
            f"Automatisk scan: {len(result.imported)} oprettet, "
            f"{result.already_present} fandtes i forvejen",
        )


async def run_auto_import_loop() -> None:
    """Baggrunds-task startet én gang fra `main.py`s lifespan og kørt i hele
    appens levetid. Genbruger `import_from_plex` uændret — den eksisterende
    manuelle "Importér fra Plex"-knap (feature #90) forbliver urørt ved
    siden af, denne styrer kun om/hvor tit den samme handling også sker af
    sig selv.

    Intervallet og til/fra-kontakten (`settings.plex_auto_import_*`) læses
    friskt hver iteration i stedet for én gang ved opstart — samme
    "settings er en levende singleton"-princip som resten af appen, så en
    admin-ændring via `PATCH /api/settings/plex-auto-import` slår igennem
    uden genstart. Bevidst intet scan lige ved opstart: en admin der
    aktiverer funktionen kan allerede trykke den eksisterende manuelle knap
    for en øjeblikkelig scan, og et automatisk scan ved hver app-genstart
    ville betyde flere unødvendige Plex-kald pr. dag hver gang serveren
    genstartes (fx ved en deploy). `asyncio.CancelledError` (ved
    app-nedlukning) fanges bevidst IKKE og får lov at forplante sig
    normalt."""
    db = get_database()
    while True:
        interval_minutes = max(settings.plex_auto_import_interval_minutes, 1)
        await asyncio.sleep(interval_minutes * 60)

        if not settings.plex_auto_import_enabled:
            continue

        await _run_one_auto_import_cycle(db)


async def get_available_ids(db: AsyncIOMotorDatabase, kind: str) -> set[str] | None:
    """Feature #156 — id-sættet bag Plex-filter-badget i biblioteks-filteret.

    `None` betyder Plex ikke er konfigureret eller kunne ikke nås — adskilt
    fra et tomt sæt (som legitimt betyder "konfigureret, men intet matcher"),
    så den kaldende service-funktion kan afvise filteret eksplicit i stedet
    for at lade et Plex-udfald stille blive tolket som "biblioteket er tomt".
    Genbruger `_match` mod hele biblioteket, samme som `get_availability_map`,
    men returnerer kun id-mængden — den fulde `PlexAvailability` er ikke
    nødvendig her, kun "er den med eller ej"."""
    if not plex_client.is_configured():
        return None

    index = await _get_index()
    if not index.result.ok:
        return None

    ids: set[str] = set()
    for doc in await _library_docs(db, kind):
        availability = _availability(
            index, kind, doc.get("tmdb_id"), _doc_title(doc, kind), doc.get("year")
        )
        if availability is not None:
            ids.add(str(doc["_id"]))
    return ids


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
