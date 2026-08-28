import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.errors import (
    ClassificationRequiredError,
    DuplicateBarcodeError,
    MovieNotFoundError,
    NotAuthorizedError,
    PlexFilterUnavailableError,
    SerialNumberConflictError,
    TmdbNotFoundError,
    TmdbRateLimitedError,
    TmdbUnavailableError,
    WishlistNotPendingError,
)
from app.integrations import omdb_client, tmdb_client
from app.models.movie import (
    CollectionInfo,
    CollectionPart,
    CollectionStats,
    DeletedMovie,
    DeletedMoviePage,
    DuplicateMatch,
    MediaType,
    Movie,
    MovieCreate,
    MoviePage,
    MoviePreview,
    MovieUpdate,
    NamedCount,
    SerialHolder,
    TmdbSyncResult,
    WishlistStatus,
    coerce_subtitles,
)
from app.models.settings import FreeSerialNumbers, SerialNumberConfig, SerialNumberConfigUpdate
from app.repositories import (
    digital_serial_repository,
    movie_repository,
    screening_repository,
    screening_request_repository,
    tv_show_repository,
)
from app.repositories.sort_title import strip_leading_article
from app.services import message_service, tag_service


def _to_model(document: dict) -> Movie:
    return Movie(
        id=str(document["_id"]),
        serial_number=document.get("serial_number"),
        tmdb_id=document.get("tmdb_id"),
        barcode=document.get("barcode"),
        barcode_source=document.get("barcode_source"),
        title=document["title"],
        year=document.get("year"),
        poster_url=document.get("poster_url"),
        overview=document.get("overview"),
        genres=document.get("genres", []),
        cast=document.get("cast", []),
        director=document.get("director"),
        tags=document.get("tags", []),
        format=document.get("format"),
        audio_types=document.get("audio_types", []),
        media_type=document.get("media_type"),
        rating=document.get("rating"),
        runtime=document.get("runtime"),
        imdb_url=document.get("imdb_url"),
        trailer_url=document.get("trailer_url"),
        location=document.get("location"),
        owner=document.get("owner"),
        subtitles=coerce_subtitles(document.get("subtitles")),
        order_status=document.get("order_status"),
        registered_by=document.get("registered_by"),
        is_wishlist=document.get("is_wishlist", False),
        wishlist_status=document.get("wishlist_status"),
        name_in_library=document.get("name_in_library"),
        personal_rating=document.get("personal_rating"),
        personal_note=document.get("personal_note"),
        watched=document.get("watched", False),
        watched_at=document.get("watched_at"),
        collection_id=document.get("collection_id"),
        collection_name=document.get("collection_name"),
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


async def _resolve_rating(details: dict) -> float | None:
    """Prefers the real IMDb rating (via OMDb) over TMDb's own vote_average
    when available (feature #46) — falls back to TMDb's rating if OMDb is
    unconfigured, unavailable, or has nothing for this imdb_id, so the
    feature degrades to "same as before" rather than losing the rating
    entirely."""
    imdb_rating = await omdb_client.get_imdb_rating(details.get("imdb_id"))
    return imdb_rating if imdb_rating is not None else details["rating"]


async def preview_from_tmdb(tmdb_id: int) -> MoviePreview:
    """Feature #79 — samme TMDb-opslag+rating-beregning som `create_movie`
    selv bruger, men rent læsende: intet oprettes. Lader scan-flowet vise
    den fulde rediger-boks for en kandidat, før brugeren har bekræftet
    noget som helst."""
    details = await tmdb_client.get_movie_details(tmdb_id)
    return MoviePreview(
        tmdb_id=details["tmdb_id"],
        title=details["title"],
        year=details["year"],
        poster_url=details["poster_url"],
        overview=details["overview"],
        genres=details["genres"],
        cast=details["cast"],
        director=details["director"],
        rating=await _resolve_rating(details),
        runtime=details["runtime"],
        imdb_url=details["imdb_url"],
        trailer_url=details["trailer_url"],
        collection_id=details["collection_id"],
        collection_name=details["collection_name"],
    )


# BUGS.md #62 — genbrug af frigjorte serienumre (feature #131) er ikke atomisk
# som tælleren, så to samtidige oprettelser kan gribe samme frigjorte nummer.
SERIAL_ASSIGN_RETRY_LIMIT = 3


def _is_serial_collision(exc: DuplicateKeyError) -> bool:
    """BUGS.md #62 — skelner en serienr-index-kollision fra en stregkode-
    kollision. `keyPattern` er den robuste kilde (ægte pymongo); en streng-
    fallback dækker mongomock/afvigende driver-versioner."""
    details = getattr(exc, "details", None) or {}
    key_pattern = details.get("keyPattern") or {}
    if "serial_number" in key_pattern:
        return True
    return "serial_number" in str(exc)


# Feature #139 — ejere hvis poster bruger de normale M/T/D-serier. Alt andet
# (og som ikke er oprettet af en admin) får den delte 5000+-pulje. Normaliseret
# med små bogstaver + mellemrum fjernet, så "Jan & Lis" == "jan&lis".
STANDARD_OWNERS = {"jan", "lis", "jan&lis", "lis&jan"}


def _normalize_owner(owner: str | None) -> str:
    return (owner or "").lower().replace(" ", "")


def _uses_other_pool(owner: str | None, creator_is_admin: bool) -> bool:
    """Feature #139 — den delte 5000+-pulje bruges kun når ejeren IKKE er en
    jan/lis-variant OG posten ikke er oprettet af en admin (Jans regel
    2026-08-13: *"hvis ejer stå til alt andet end jan/lis/jan&lis/Lis&jan skal
    serie nr tildeles 5000 og op efter ... eller det er en admin så er det også
    standart serie nr. serie"*)."""
    if creator_is_admin:
        return False
    return _normalize_owner(owner) not in STANDARD_OWNERS


async def _assign_serial_number(
    db, is_wishlist: bool, media_type, owner: str | None, creator_is_admin: bool
) -> int | None:
    """Tildeler et serienummer fra den rigtige serie, eller None.

    Feature #92 gav kun fysiske udgaver et nummer; feature #93 gav digitale
    deres egen serie i stedet (Jans ønske 2026-08-08). Ønskelisten står
    fortsat udenfor — man ejer ikke det man ønsker sig endnu.

    Tre serier tælles hver for sig: fysiske film (M#), fysiske TV-serier
    (T#) og *alle* digitale udgaver under ét (D#, delt på tværs af film og
    serier, så et D#-nummer altid peger på præcis én ting).

    Feature #139 — poster hvis ejer ikke er en jan/lis-variant, og som ikke er
    oprettet af en admin, får i stedet nummer fra den delte 5000+-pulje
    (`next_other_serial_number`) uanset fysisk/digital.

    `media_type` er påkrævet ved oprettelse af en biblioteks-post, så "ikke
    sat" kan kun forekomme på dokumenter fra før den regel. De får intet
    nummer her; eksisterende dokumenter røres kun af migreringen i
    `digital_serial_repository.backfill`."""
    if is_wishlist:
        return None
    if _uses_other_pool(owner, creator_is_admin):
        return await digital_serial_repository.next_other_serial_number(db)
    if media_type == MediaType.PHYSICAL:
        return await movie_repository.next_serial_number(db)
    if media_type == MediaType.DIGITAL:
        return await digital_serial_repository.next_serial_number(db)
    return None


# `creator_is_admin` defaulter til True (→ standard M/T/D-serie), så en kalder
# der udelader den aldrig utilsigtet havner i 5000+-puljen; API-laget sender den
# faktiske værdi (feature #139).
async def create_movie(
    db: AsyncIOMotorDatabase,
    payload: MovieCreate,
    registered_by: str,
    creator_is_admin: bool = True,
) -> Movie:
    canonical_tags = await tag_service.resolve_tags(
        db, [*payload.tags, tag_service.added_by_tag(registered_by)]
    )
    now = datetime.now(timezone.utc)

    if payload.tmdb_id is not None:
        details = await tmdb_client.get_movie_details(payload.tmdb_id)
        movie_fields = {
            "tmdb_id": details["tmdb_id"],
            "title": details["title"],
            "year": details["year"],
            "poster_url": details["poster_url"],
            "overview": details["overview"],
            "genres": details["genres"],
            "cast": details["cast"],
            "director": details["director"],
            "rating": await _resolve_rating(details),
            "runtime": details["runtime"],
            "imdb_url": details["imdb_url"],
            "trailer_url": details["trailer_url"],
            "collection_id": details["collection_id"],
            "collection_name": details["collection_name"],
        }
    else:
        movie_fields = {
            "tmdb_id": None,
            "title": payload.title,
            "year": payload.year,
            "poster_url": payload.poster_url,
            "overview": payload.overview,
            "genres": payload.genres,
            "cast": payload.cast,
            "director": payload.director,
            "rating": None,
            "runtime": payload.runtime,
            "imdb_url": payload.imdb_url,
            "trailer_url": payload.trailer_url,
        }

    document = {
        **movie_fields,
        "tags": canonical_tags,
        "tags_normalized": [tag_service.normalize(tag) for tag in canonical_tags],
        # Feature #184 — sorterings-nøgle der ignorerer en foranstillet "The".
        "sort_title": strip_leading_article(movie_fields["title"]),
        "format": payload.format.value if payload.format else None,
        "audio_types": [audio_type.value for audio_type in payload.audio_types],
        "media_type": payload.media_type.value if payload.media_type else None,
        "location": payload.location,
        "owner": payload.owner or registered_by,
        "subtitles": coerce_subtitles(payload.subtitles),
        "order_status": payload.order_status.value if payload.order_status else None,
        "registered_by": registered_by,
        "is_wishlist": payload.is_wishlist,
        # Feature #144 — et ønske fra en ikke-admin afventer godkendelse; en
        # admins (og biblioteks-poster får slet ingen status).
        "wishlist_status": (
            (WishlistStatus.APPROVED.value if creator_is_admin else WishlistStatus.PENDING.value)
            if payload.is_wishlist
            else None
        ),
        "created_at": now,
        "updated_at": now,
    }
    # Kun fysiske udgaver i biblioteket nummereres (feature #92, Jans krav
    # 2026-08-08): serienummeret svarer til en plads på en hylde, og en
    # digital kopi står ingen steder. Ønskelisten er også udenfor — man ejer
    # ikke det man ønsker sig endnu.
    #
    # Nøglen udelades helt frem for at sættes til null (samme "absent, not
    # null"-mønster som `barcode`, se BUGS.md #1/#10), så det sparse unikke
    # index på `serial_number` aldrig ser en kollision mellem to poster uden
    # nummer.
    trimmed_barcode = payload.barcode.strip() if payload.barcode else ""
    if trimmed_barcode:
        document["barcode"] = trimmed_barcode
    # Feature #77 — samme "udelad frem for null"-mønster som barcode selv:
    # kun ægte scan-matches sætter dette, aldrig manuel/tmdb-direkte oprettelse.
    if payload.barcode_source:
        document["barcode_source"] = payload.barcode_source

    # BUGS.md #62 — tildel serienummer og indsæt i én løkke: rammer en serienr-
    # kollision (samtidig oprettelse der greb samme frigjorte nummer), tildeles
    # et frisk nummer og forsøges igen; kun en ægte stregkode-kollision mapper
    # til DuplicateBarcodeError.
    for _attempt in range(SERIAL_ASSIGN_RETRY_LIMIT):
        serial_number = await _assign_serial_number(
            db,
            payload.is_wishlist,
            payload.media_type,
            payload.owner or registered_by,
            creator_is_admin,
        )
        if serial_number is not None:
            document["serial_number"] = serial_number
        try:
            created = await movie_repository.insert(db, document)
            return _to_model(created)
        except DuplicateKeyError as exc:
            if _is_serial_collision(exc):
                continue
            raise DuplicateBarcodeError(trimmed_barcode) from exc
    raise SerialNumberConflictError(
        "Kunne ikke finde et ledigt serienummer efter flere forsøg"
    )


def parse_sort_param(sort: str | None) -> list[tuple[str, int]]:
    """Parses up to `movie_repository.MAX_SORT_LEVELS` comma-separated
    "field:direction" tokens (direction optional, defaults to asc) into a
    compound Mongo sort spec — see FEATURES.md #17/#27. Unknown fields are
    silently dropped rather than rejected, since a saved preset referencing a
    since-removed field should degrade gracefully instead of erroring."""
    if not sort:
        return []
    levels: list[tuple[str, int]] = []
    for token in sort.split(",")[: movie_repository.MAX_SORT_LEVELS]:
        field, _, direction = token.partition(":")
        keys = movie_repository.SORT_FIELDS.get(field)
        if keys is None:
            continue
        user_direction = -1 if direction == "desc" else 1
        # Feature #96 — ét valg kan udvide til flere mongo-nøgler (fx serie
        # + nummer). "user" følger op/ned-knappen; en fast retning gør ikke.
        for mongo_field, mode in keys:
            if mode == "user":
                levels.append((mongo_field, user_direction))
            else:
                levels.append((mongo_field, -1 if mode == "desc" else 1))
    return levels


async def _resolve_plex_id_filter(db: AsyncIOMotorDatabase, plex: bool | None) -> dict:
    """Feature #156 — Plex-badget i filter-panelet. Lokalt import af
    `plex_service` (i stedet for et modul-top import) fordi `plex_service`
    selv importerer `movie_service`/`tv_show_service` (til `_create_imported`,
    feature #90) — et top-level import her ville give et cirkulært import.
    Returnerer `{}` når `plex` er `None` (intet Plex-filter anvendt)."""
    if plex is None:
        return {}
    from app.services import plex_service

    available_ids = await plex_service.get_available_ids(db, "movie")
    if available_ids is None:
        raise PlexFilterUnavailableError()
    return {"id_in": list(available_ids)} if plex else {"id_nin": list(available_ids)}


async def list_movies(
    db: AsyncIOMotorDatabase,
    q: str | None,
    tags: list[str] | None,
    formats: list[str] | None = None,
    audio_types: list[str] | None = None,
    media_types: list[str] | None = None,
    sort: str | None = None,
    is_wishlist: bool = False,
    watched: bool | None = None,
    cast: str | None = None,
    director: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    genres: list[str] | None = None,
    tags_exclude: list[str] | None = None,
    formats_exclude: list[str] | None = None,
    audio_types_exclude: list[str] | None = None,
    media_types_exclude: list[str] | None = None,
    genres_exclude: list[str] | None = None,
    plex: bool | None = None,
    order_statuses: list[str] | None = None,
    order_statuses_exclude: list[str] | None = None,
) -> MoviePage:
    """`page`/`page_size` omitted (the default) fetches every match, no cap
    — used by callers that need the whole filtered set (Print-siden, Voldby
    BIO's søgning), not just the biblioteks-visningens aktuelle side
    (feature #15)."""
    normalized_tags = [tag_service.normalize(tag) for tag in (tags or []) if tag.strip()]
    normalized_tags_exclude = [
        tag_service.normalize(tag) for tag in (tags_exclude or []) if tag.strip()
    ]
    sort_spec = parse_sort_param(sort)
    paginating = page is not None and page_size is not None
    skip = (page - 1) * page_size if paginating else 0
    limit = page_size if paginating else None

    filters = {
        "query": q,
        "tags": normalized_tags or None,
        "tags_exclude": normalized_tags_exclude or None,
        "formats": formats or None,
        "formats_exclude": formats_exclude or None,
        "audio_types": audio_types or None,
        "audio_types_exclude": audio_types_exclude or None,
        "media_types": media_types or None,
        "media_types_exclude": media_types_exclude or None,
        "genres": genres or None,
        "genres_exclude": genres_exclude or None,
        "order_statuses": order_statuses or None,
        "order_statuses_exclude": order_statuses_exclude or None,
        "is_wishlist": is_wishlist,
        "watched": watched,
        "cast": cast,
        "director": director,
        **(await _resolve_plex_id_filter(db, plex)),
    }

    documents = await movie_repository.find_many(db, filters, sort_spec or None, skip, limit)
    # Feature #145 — markér ønsker hvis titlen falder sammen med en titel der
    # allerede er i biblioteket (film ELLER TV). Kun i ønske-visningen, og kun
    # ét sæt-opslag pr. side frem for ét pr. post.
    if is_wishlist and documents:
        library_titles = await movie_repository.library_titles_normalized(db)
        library_titles |= await tv_show_repository.library_titles_normalized(db)
        for doc in documents:
            title = (doc.get("title") or "").strip().lower()
            doc["name_in_library"] = bool(title) and title in library_titles

    items = [_to_model(doc) for doc in documents]

    if paginating:
        total = await movie_repository.count_many(db, filters)
    else:
        total = len(items)

    return MoviePage(items=items, total=total)


async def list_genres(db: AsyncIOMotorDatabase) -> list[str]:
    """Feature #111 — se `movie_repository.distinct_genres`'s docstring."""
    return await movie_repository.distinct_genres(db)


async def get_collection_info(db: AsyncIOMotorDatabase, collection_id: int) -> CollectionInfo:
    collection = await tmdb_client.get_collection(collection_id)
    tmdb_ids = [part["tmdb_id"] for part in collection["parts"]]
    owned_docs = await movie_repository.find_by_tmdb_ids(db, tmdb_ids)
    owned_by_tmdb_id = {doc["tmdb_id"]: doc for doc in owned_docs}

    parts = []
    for part in collection["parts"]:
        owned_doc = owned_by_tmdb_id.get(part["tmdb_id"])
        parts.append(
            CollectionPart(
                tmdb_id=part["tmdb_id"],
                title=part["title"],
                year=part["year"],
                poster_url=part["poster_url"],
                owned=owned_doc is not None,
                owned_movie_id=str(owned_doc["_id"]) if owned_doc else None,
                owned_is_wishlist=owned_doc.get("is_wishlist", False) if owned_doc else False,
            )
        )
    return CollectionInfo(
        id=collection["id"], name=collection["name"], poster_url=collection["poster_url"], parts=parts
    )


# Feature #77 — samme fire nøgler som scan_service.BARCODE_SOURCES, mappet
# til de menneskelæsbare navne Statistik-siden viser.
_BARCODE_SOURCE_LABELS = {
    "upcitemdb": "UPCitemdb",
    "discogs": "Discogs",
    "upcdatabase": "UPCDatabase.org",
    "ean_search": "EAN-Search.org",
}

# Feature #159 — sidste kvartals tendens er nyttig at se på ét blik; alle
# uger siden begyndelsen ville hverken være læsbart i en simpel bar-liste
# eller særlig interessant (samme afvejning som top_directors/top_actors'
# most_common(10) ovenfor).
WEEKLY_ADDITIONS_WEEKS = 12


def _iso_week_key(moment: datetime) -> tuple[int, int]:
    iso = moment.isocalendar()
    return (iso[0], iso[1])


def _recent_iso_weeks(count: int) -> list[tuple[int, int]]:
    """De seneste `count` ISO-uger (år, uge), kronologisk, sluttende med den
    aktuelle uge. `timedelta(weeks=i)` lander altid i en anden kalenderuge
    end nabo-i'erne, så år-skiftet omkring nytår håndteres korrekt af
    `isocalendar()` selv — ingen særlig kant-håndtering nødvendig her."""
    now = datetime.now(timezone.utc)
    return [_iso_week_key(now - timedelta(weeks=i)) for i in range(count - 1, -1, -1)]


async def get_collection_stats(db: AsyncIOMotorDatabase) -> CollectionStats:
    """Aggregated statistics over the whole library (wishlist excluded) —
    computed in Python over a single find() rather than a Mongo aggregation
    pipeline, matching this codebase's existing style and sidestepping any
    mongomock aggregation-pipeline gaps in the test suite (see BUGS.md's
    notes on mongomock's sparse-index/arrayFilters inconsistencies — the
    same caution applies to untested pipeline stages)."""
    documents = await movie_repository.find_all_library_movies(db)
    # Feature #77 — dækker film+TV, se find_all_library_tv_shows.
    tv_documents = await tv_show_repository.find_all_library_tv_shows(db)

    total_movies = len(documents)
    watched_count = sum(1 for doc in documents if doc.get("watched"))

    genre_counter: Counter[str] = Counter()
    decade_counter: Counter[int] = Counter()
    format_counter: Counter[str] = Counter()
    director_counter: Counter[str] = Counter()
    actor_counter: Counter[str] = Counter()
    barcode_source_counter: Counter[str] = Counter()
    # Feature #159 — dækker film+TV, samme "begge tæller med"-princip som
    # barcode_source_counter ovenfor.
    weekly_counter: Counter[tuple[int, int]] = Counter()

    for doc in documents:
        genre_counter.update(doc.get("genres", []))
        actor_counter.update(doc.get("cast", []))
        if doc.get("year"):
            decade_counter[(doc["year"] // 10) * 10] += 1
        if doc.get("format"):
            format_counter[doc["format"]] += 1
        if doc.get("director"):
            director_counter[doc["director"]] += 1
        if doc.get("barcode_source"):
            barcode_source_counter[doc["barcode_source"]] += 1
        if doc.get("created_at"):
            weekly_counter[_iso_week_key(doc["created_at"])] += 1

    for doc in tv_documents:
        if doc.get("barcode_source"):
            barcode_source_counter[doc["barcode_source"]] += 1
        if doc.get("created_at"):
            weekly_counter[_iso_week_key(doc["created_at"])] += 1

    return CollectionStats(
        total_movies=total_movies,
        total_runtime_minutes=sum(doc.get("runtime") or 0 for doc in documents),
        watched_count=watched_count,
        unwatched_count=total_movies - watched_count,
        genre_breakdown=[
            NamedCount(name=name, count=count)
            for name, count in sorted(genre_counter.items(), key=lambda item: -item[1])
        ],
        decade_breakdown=[
            NamedCount(name=f"{decade}'erne", count=count)
            for decade, count in sorted(decade_counter.items())
        ],
        format_breakdown=[
            NamedCount(name=name, count=count)
            for name, count in sorted(format_counter.items(), key=lambda item: -item[1])
        ],
        top_directors=[
            NamedCount(name=name, count=count) for name, count in director_counter.most_common(10)
        ],
        top_actors=[
            NamedCount(name=name, count=count) for name, count in actor_counter.most_common(10)
        ],
        barcode_source_breakdown=[
            NamedCount(name=_BARCODE_SOURCE_LABELS.get(key, key), count=count)
            for key, count in sorted(barcode_source_counter.items(), key=lambda item: -item[1])
        ],
        weekly_additions=[
            NamedCount(name=f"Uge {week}", count=weekly_counter.get((year, week), 0))
            for year, week in _recent_iso_weeks(WEEKLY_ADDITIONS_WEEKS)
        ],
    )


async def check_tmdb_duplicates(db: AsyncIOMotorDatabase, tmdb_id: int) -> list[DuplicateMatch]:
    documents = await movie_repository.find_by_tmdb_id(db, tmdb_id)
    return [
        DuplicateMatch(
            id=str(doc["_id"]),
            title=doc["title"],
            serial_number=doc.get("serial_number"),
            is_wishlist=doc.get("is_wishlist", False),
            media_type=doc.get("media_type"),
        )
        for doc in documents
    ]


async def get_movie(db: AsyncIOMotorDatabase, movie_id: str) -> Movie:
    document = await movie_repository.find_by_id(db, movie_id)
    if document is None:
        raise MovieNotFoundError(movie_id)
    return _to_model(document)


_TEMP_SERIAL_NUMBER = -1


async def _reassign_serial_number(
    db: AsyncIOMotorDatabase, movie_id: str, current_doc: dict, new_serial: int
) -> None:
    """Swap with whichever item currently holds `new_serial` *in the same
    series*, if any — serial numbers are unique per series, so a direct move
    would otherwise raise a duplicate-key error. See BUGS.md #56 for why the
    lookup must be series-aware (a plain by-number lookup could grab a post from
    another series — a digital D#10 while editing a physical M#16 — and either
    renumber the wrong item or, with both series present, hit a duplicate key).
    The digital series is shared across movies and TV shows, so the holder can
    live in the *other* collection; the swap writes back wherever it is.

    Trades a hop through a sentinel value instead of a single atomic update
    (Mongo has no built-in "swap two unique values" without transactions, and
    this app runs against a standalone MongoDB). A concurrent write can still
    race in between — that surfaces as `SerialNumberConflictError` (a clean
    409) rather than a raw 500."""
    old_serial = current_doc["serial_number"]
    if new_serial == old_serial:
        return

    holder = await digital_serial_repository.find_series_holder(
        db,
        current_doc.get("media_type"),
        new_serial,
        movie_repository.COLLECTION,
        current_doc["_id"],
    )
    try:
        if holder is not None:
            collection_name, doc = holder
            await movie_repository.set_serial_number(db, movie_id, _TEMP_SERIAL_NUMBER)
            await digital_serial_repository.set_serial(
                db, collection_name, doc["_id"], old_serial
            )
        await movie_repository.set_serial_number(db, movie_id, new_serial)
    except DuplicateKeyError as exc:
        raise SerialNumberConflictError(new_serial) from exc


async def find_serial_swap_target(
    db: AsyncIOMotorDatabase, movie_id: str, new_serial: int
) -> SerialHolder:
    """BUGS.md #56 — hvem holder `new_serial` i samme serie som filmen `movie_id`?
    Bruges af bibliotekets byt-plads-bekræftelse: er nummeret optaget, skal
    brugeren først se hvilken titel de to bytter plads med. Titlen kan komme fra
    den anden collection (en digital TV-serie), da den digitale serie er delt."""
    current_doc = await movie_repository.find_by_id(db, movie_id)
    if current_doc is None:
        raise MovieNotFoundError(movie_id)
    if current_doc.get("serial_number") == new_serial:
        return SerialHolder(title=None)

    holder = await digital_serial_repository.find_series_holder(
        db,
        current_doc.get("media_type"),
        new_serial,
        movie_repository.COLLECTION,
        current_doc["_id"],
    )
    if holder is None:
        return SerialHolder(title=None)
    _, doc = holder
    # Film har `title`, TV-serier `name` — den delte digitale serie kan give en
    # holder af hver slags.
    return SerialHolder(title=doc.get("title") or doc.get("name"))


def _assert_can_edit_serial_number(current_user: dict, movie_doc: dict) -> None:
    """Only an admin or the user who originally registered this specific movie
    may renumber it — enforced here (backend), not just hidden/disabled in the
    UI, per CLAUDE.md regel 16 (adgangskontrol-lockout/håndhævelse)."""
    is_admin = current_user.get("role") == "admin"
    is_registrant = movie_doc.get("registered_by") == current_user.get("username")
    if not (is_admin or is_registrant):
        raise NotAuthorizedError(
            "Kun en admin eller den bruger der registrerede filmen kan ændre serienummeret"
        )


async def update_movie(
    db: AsyncIOMotorDatabase, movie_id: str, payload: MovieUpdate, current_user: dict
) -> Movie:
    # BUGS.md #59 — bevidst IKKE mode="json": det ville serialisere `watched_at`
    # (et datetime) til en ISO-streng før den rå `$set`, så feltet gemmes som
    # streng frem for Date (samme korruption som BUGS.md #33's scheduled_at).
    # Enum-felterne (format/audio_types/media_type) er `str`-enums og gemmes
    # korrekt som strenge uden mode="json".
    fields = payload.model_dump(exclude_unset=True)

    # Feature #144 — kun en admin må godkende et ønske (sætte wishlist_status).
    # Håndhæves i backend (regel 16), ikke kun ved at skjule knappen i UI'et.
    if "wishlist_status" in fields and current_user.get("role") != "admin":
        raise NotAuthorizedError("Kun en admin kan godkende ønsker")

    if "tags" in fields:
        canonical_tags = await tag_service.resolve_tags(db, fields["tags"])
        fields["tags"] = canonical_tags
        fields["tags_normalized"] = [tag_service.normalize(tag) for tag in canonical_tags]

    # Feature #184 — holder sort_title ved lige når titlen redigeres direkte.
    if "title" in fields:
        fields["sort_title"] = strip_leading_article(fields["title"])

    # Feature #123 — trim/drop-tomme, så en opdatering gemmer samme rene
    # liste-form som oprettelsen (coerce er en no-op på en allerede-ren liste).
    if "subtitles" in fields:
        fields["subtitles"] = coerce_subtitles(fields["subtitles"])

    requested_serial = fields.pop("serial_number", None)
    requested_wishlist = fields.pop("is_wishlist", None)
    requested_media_type = fields.get("media_type")
    requested_wishlist_status = fields.get("wishlist_status")
    requested_order_status = fields.get("order_status")

    current_doc = None
    if (
        requested_serial is not None
        or requested_wishlist is not None
        or requested_media_type is not None
        or requested_wishlist_status is not None
        or requested_order_status is not None
    ):
        current_doc = await movie_repository.find_by_id(db, movie_id)
        if current_doc is None:
            raise MovieNotFoundError(movie_id)

    # Feature #141 — flyttes et ønske ind i biblioteket, får den der satte det
    # på ønskelisten besked (efter selve skrivningen, nederst i funktionen).
    moved_to_library = False
    if requested_wishlist is not None:
        was_wishlist = current_doc.get("is_wishlist", False)
        fields["is_wishlist"] = requested_wishlist
        # Feature #92 — medietypen efter opdateringen, ikke den gemte: flyttes
        # en post til biblioteket i samme kald som medietypen sættes, er det
        # den nye værdi der afgør om der skal tildeles et nummer.
        media_type = requested_media_type or current_doc.get("media_type")
        if was_wishlist and not requested_wishlist:
            moved_to_library = True
            # Feature #196 — samme krav som MovieCreate.
            # require_media_type_and_format_for_library, håndhævet her fordi
            # "flyt til bibliotek" er den samme overgang som at oprette
            # biblioteks-posten (se ClassificationRequiredError).
            format_value = fields.get("format") or current_doc.get("format")
            missing = []
            if not media_type:
                missing.append("media_type")
            if not format_value:
                missing.append("format")
            if missing:
                raise ClassificationRequiredError(missing)
            # Moving from the wishlist into the real collection (feature
            # #28/#32) — assign a fresh serial number, same as at creation.
            # Unrestricted, like POST /api/movies: this isn't "editing" an
            # existing number, it's assigning the first one. Kun hvis den
            # faktisk er fysisk (feature #92).
            assigned = await _assign_serial_number(
                db,
                False,
                media_type,
                fields.get("owner", current_doc.get("owner")),
                current_user.get("role") == "admin",
            )
            if assigned is not None:
                fields["serial_number"] = assigned
        elif not was_wishlist and requested_wishlist:
            # The reverse direction strips an existing serial number, which
            # is at least as sensitive as changing one — same gate applies.
            _assert_can_edit_serial_number(current_user, current_doc)
            await movie_repository.clear_serial_number(db, movie_id)
    elif requested_serial is not None:
        _assert_can_edit_serial_number(current_user, current_doc)
        await _reassign_serial_number(db, movie_id, current_doc, requested_serial)
    elif requested_media_type is not None:
        # Feature #92 — reglen håndhæves begge veje (Jans valg 2026-08-08).
        # Skifter en fysisk udgave til digital, giver dens nummer ikke længere
        # mening og frigives; går den den anden vej, tildeles et nyt. Uden
        # dette ville reglen kun holde på oprettelses-tidspunktet, og der
        # kunne ligge digitale poster med numre bagefter.
        # Feature #93 — medietypen bestemmer *hvilken* serie nummeret hører
        # til, ikke bare om der er et. Et skift mellem fysisk og digital
        # flytter derfor posten til den anden serie: det gamle nummer
        # frigives, og et nyt tildeles fra den rigtige.
        was_digital = current_doc.get("media_type") == MediaType.DIGITAL.value
        is_digital = requested_media_type == MediaType.DIGITAL.value
        series_changed = was_digital != is_digital
        assigned = await _assign_serial_number(
            db,
            current_doc.get("is_wishlist", False),
            requested_media_type,
            fields.get("owner", current_doc.get("owner")),
            current_user.get("role") == "admin",
        )
        has_now = current_doc.get("serial_number") is not None
        if assigned is not None and (not has_now or series_changed):
            fields["serial_number"] = assigned
        elif assigned is None and has_now:
            _assert_can_edit_serial_number(current_user, current_doc)
            await movie_repository.clear_serial_number(db, movie_id)

    fields["updated_at"] = datetime.now(timezone.utc)

    document = await movie_repository.update(db, movie_id, fields)
    if document is None:
        raise MovieNotFoundError(movie_id)
    if moved_to_library:
        await message_service.notify_wishlist_moved(
            db, current_doc, current_user, document.get("title"), is_tv=False
        )
    # Feature #166 — modparten til #165's afvisnings-besked: godkendes et
    # afventende ønske, får opretteren også besked om det. `current_doc`s
    # status er den FØR skrivningen, så et allerede-godkendt ønske (fx et
    # dobbeltklik) ikke sender endnu en besked.
    if (
        requested_wishlist_status == WishlistStatus.APPROVED.value
        and current_doc is not None
        and current_doc.get("wishlist_status") == WishlistStatus.PENDING.value
    ):
        await message_service.notify_wishlist_approved(
            db, current_doc, current_user, document.get("title"), is_tv=False
        )
    # Feature #189 — Jan: "hvis så en adm ændre film/tv til at den er
    # bestilt så skal user have besked". Kun ved selve OVERGANGEN til bestilt
    # (ikke-bestilt → bestilt), og kun mens ønsket stadig er på indkøbslisten
    # — samme afgrænsning som #166s pending→approved, så et skift af
    # bestillingssted på et allerede bestilt ønske ikke giver en ny besked.
    if (
        requested_order_status is not None
        and current_doc is not None
        and current_doc.get("is_wishlist")
        and not current_doc.get("order_status")
    ):
        await message_service.notify_wishlist_ordered(
            db, current_doc, current_user, document.get("title"), is_tv=False
        )
    return _to_model(document)


async def delete_movie(db: AsyncIOMotorDatabase, movie_id: str, deleted_by: str) -> None:
    document = await movie_repository.find_by_id(db, movie_id)
    if document is None:
        raise MovieNotFoundError(movie_id)

    await movie_repository.archive_deleted(db, document, deleted_by)
    deleted = await movie_repository.delete(db, movie_id)
    if not deleted:
        raise MovieNotFoundError(movie_id)

    # BUGS.md #43 — screenings/requests reference the movie by id and resolve
    # their title/poster at read time, so leaving them behind turns them into
    # untitled ghost cards in the Voldby BIO programme (including the public
    # /bio page). `reset_library` already clears both collections for exactly
    # this reason when wiping the whole library; single-item deletion has to
    # do the same for its own title.
    await screening_repository.delete_for_title(db, "movie", movie_id)
    await screening_request_repository.delete_for_title(db, "movie", movie_id)


async def reject_wishlist_movie(
    db: AsyncIOMotorDatabase, movie_id: str, admin: dict, message: str | None
) -> None:
    """Feature #165 — modparten til at godkende et ønske (feature #144):
    admin må også sige nej. Fjerner ønsket helt (samme sletning som en
    almindelig sletning, ikke en tredje wishlist_status-værdi den skal
    filtreres/vises et sted) og giver opretteren besked hvorfor. Kun
    reachable via en admin-only rute (`dependencies=[Depends(require_admin)]`
    i api/movies.py) — rollen tjekkes derfor ikke igen her, i modsætning til
    update_movie's wishlist_status-gren, som deler en generisk rute med
    alle andre felt-opdateringer."""
    document = await movie_repository.find_by_id(db, movie_id)
    if document is None:
        raise MovieNotFoundError(movie_id)
    if not document.get("is_wishlist") or document.get("wishlist_status") != WishlistStatus.PENDING.value:
        raise WishlistNotPendingError(movie_id)

    await delete_movie(db, movie_id, admin["username"])
    await message_service.notify_wishlist_rejected(
        db, document, admin, document.get("title"), is_tv=False, reason=message
    )


async def list_deleted_movies(
    db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 1000
) -> DeletedMoviePage:
    documents = await movie_repository.list_deleted(db, skip, limit)
    total = await movie_repository.count_deleted(db)
    return DeletedMoviePage(
        entries=[
            DeletedMovie(
                id=str(doc["_id"]),
                serial_number=doc.get("serial_number"),
                title=doc["title"],
                year=doc.get("year"),
                format=doc.get("format"),
                deleted_at=doc["deleted_at"],
                deleted_by=doc.get("deleted_by"),
            )
            for doc in documents
        ],
        total=total,
    )


async def sync_all_from_tmdb(db: AsyncIOMotorDatabase) -> TmdbSyncResult:
    """Re-fetches every TMDb-sourced movie's cached metadata (title, year,
    poster, overview, genres, cast, director, rating — real IMDb rating via
    OMDb when available, TMDb's vote_average otherwise, see
    _resolve_rating/feature #46 — runtime, IMDb/trailer links) from
    TMDb as it stands right now — see FEATURES.md #33. User-entered fields (tags, format,
    audio_types, location, owner, serial_number, registered_by, barcode)
    are never touched. A single movie's TMDb lookup failing (removed from
    TMDb, TMDb briefly down) does not abort the rest of the batch — it is
    counted as failed and the sync continues, matching the "catch-all for
    unexpected external-API failures" lesson in CLAUDE.md regel 16.

    Two batch-specific failure modes are handled specially rather than
    falling into the same per-movie "failed" bucket as a single missing
    title, since they aren't really about any individual movie:
    - No `TMDB_API_TOKEN` configured: every movie would fail for the exact
      same reason, so this is detected up front instead of making N
      identical failing requests.
    - TMDb rate-limits us (429) partway through: continuing would almost
      certainly fail every remaining movie too (MOVIE_API_REFERENCE.md asks
      integrations to be gentle with TMDb), so the batch stops immediately
      instead of hammering an already-throttled API."""
    documents = await movie_repository.find_all_with_tmdb_id(db)

    if not settings.tmdb_api_token:
        titles = [doc["title"] for doc in documents]
        return TmdbSyncResult(
            total=len(documents),
            synced=0,
            failed=len(titles),
            failed_titles=titles,
            stopped_early=True,
        )

    synced = 0
    failed_titles: list[str] = []
    stopped_early = False

    for index, document in enumerate(documents):
        try:
            details = await tmdb_client.get_movie_details(document["tmdb_id"])
        except TmdbRateLimitedError:
            failed_titles.extend(doc["title"] for doc in documents[index:])
            stopped_early = True
            break
        except (TmdbNotFoundError, TmdbUnavailableError):
            failed_titles.append(document["title"])
            continue

        fields = {
            "title": details["title"],
            "year": details["year"],
            "poster_url": details["poster_url"],
            "overview": details["overview"],
            "genres": details["genres"],
            "cast": details["cast"],
            "director": details["director"],
            "rating": await _resolve_rating(details),
            "runtime": details["runtime"],
            "imdb_url": details["imdb_url"],
            "trailer_url": details["trailer_url"],
            "collection_id": details["collection_id"],
            "collection_name": details["collection_name"],
            "sort_title": strip_leading_article(details["title"]),
            "updated_at": datetime.now(timezone.utc),
        }
        await movie_repository.update(db, str(document["_id"]), fields)
        synced += 1
        await asyncio.sleep(0.05)  # be gentle with TMDb across a large batch

    return TmdbSyncResult(
        total=len(documents),
        synced=synced,
        failed=len(failed_titles),
        failed_titles=failed_titles,
        stopped_early=stopped_early,
    )


async def _free_serial_numbers(db: AsyncIOMotorDatabase) -> FreeSerialNumbers:
    """Feature #131 — de ledige (frigjorte) numre pr. serie. Samles i service-
    laget, da de tre serier bor i hver sit repository."""
    return FreeSerialNumbers(
        physical_movies=await movie_repository.free_serial_numbers(db),
        physical_tv=await tv_show_repository.free_serial_numbers(db),
        digital=await digital_serial_repository.free_serial_numbers(db),
    )


async def get_serial_number_config(db: AsyncIOMotorDatabase) -> SerialNumberConfig:
    config = await movie_repository.get_serial_config(db)
    return SerialNumberConfig(**config, free_numbers=await _free_serial_numbers(db))


async def update_serial_number_config(
    db: AsyncIOMotorDatabase, payload: SerialNumberConfigUpdate
) -> SerialNumberConfig:
    updates = payload.model_dump(exclude_unset=True)
    config = await movie_repository.update_serial_config(db, updates)
    return SerialNumberConfig(**config, free_numbers=await _free_serial_numbers(db))


async def renumber_digital_serial_from_one(db: AsyncIOMotorDatabase) -> int:
    """Feature #188 — se `digital_serial_repository.renumber_from_one`s
    docstring for hele begrundelsen. Ren gennemstilling til repository-laget;
    lever her fordi API-laget kun kalder service-funktioner (ARCHITECTURE.md)."""
    return await digital_serial_repository.renumber_from_one(db)
