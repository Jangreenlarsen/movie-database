import asyncio
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.errors import (
    DuplicateBarcodeError,
    NotAuthorizedError,
    PlexFilterUnavailableError,
    SerialNumberConflictError,
    TmdbNotFoundError,
    TmdbRateLimitedError,
    TmdbUnavailableError,
    TvShowNotFoundError,
)
from app.integrations import omdb_client, tmdb_client
from app.models.movie import TmdbSyncResult
from app.models.movie import MediaType, WishlistStatus, coerce_subtitles
from app.models.tv_show import (
    DeletedTvShow,
    DuplicateTvShowMatch,
    Episode,
    Season,
    TvShow,
    TvShowCreate,
    TvShowPage,
    TvShowPreview,
    TvShowUpdate,
)
from app.repositories import (
    digital_serial_repository,
    movie_repository,
    screening_repository,
    screening_request_repository,
    tv_show_repository,
)
from app.services import message_service, tag_service


def _to_model(document: dict) -> TvShow:
    return TvShow(
        id=str(document["_id"]),
        serial_number=document.get("serial_number"),
        tmdb_id=document.get("tmdb_id"),
        barcode=document.get("barcode"),
        barcode_source=document.get("barcode_source"),
        name=document["name"],
        year=document.get("year"),
        end_year=document.get("end_year"),
        status=document.get("status"),
        poster_url=document.get("poster_url"),
        overview=document.get("overview"),
        genres=document.get("genres", []),
        cast=document.get("cast", []),
        creators=document.get("creators", []),
        tags=document.get("tags", []),
        format=document.get("format"),
        audio_types=document.get("audio_types", []),
        media_type=document.get("media_type"),
        rating=document.get("rating"),
        number_of_seasons=document.get("number_of_seasons"),
        number_of_episodes=document.get("number_of_episodes"),
        imdb_url=document.get("imdb_url"),
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
        seasons=[Season(**season) for season in document.get("seasons", [])],
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


async def _resolve_rating(details: dict) -> float | None:
    """Same IMDb-over-TMDb preference as movie_service._resolve_rating
    (feature #46) — kept as a separate copy since it operates on the
    differently-shaped TV details dict, not worth a shared helper for one
    two-line function."""
    imdb_rating = await omdb_client.get_imdb_rating(details.get("imdb_id"))
    return imdb_rating if imdb_rating is not None else details["rating"]


async def _build_seasons(
    tmdb_id: int, tmdb_seasons: list[dict], owned_season_numbers: list[int]
) -> list[dict]:
    """Marks the caller-selected seasons as owned right at creation time
    (feature #54), instead of the frontend making a separate
    POST-then-N-PATCH round trip — that had a real duplicate-creation risk
    if any of the PATCHes failed after the show already existed (BUGS.md
    #28). A TMDb failure while fetching one season's episode list is not
    fatal to creation: the season is still marked owned with an empty
    (not-yet-cached) episode list — the next toggle of that season off/on
    retries the fetch, same self-healing behavior `set_season_owned`
    already relies on."""
    owned_set = set(owned_season_numbers)
    seasons = []
    for season in tmdb_seasons:
        owned = season["season_number"] in owned_set
        episodes: list[dict] = []
        if owned:
            try:
                raw_episodes = await tmdb_client.get_season_details(
                    tmdb_id, season["season_number"]
                )
                episodes = [
                    Episode(
                        episode_number=ep["episode_number"],
                        name=ep["name"],
                        air_date=ep["air_date"],
                    ).model_dump(mode="json")
                    for ep in raw_episodes
                ]
            except (TmdbNotFoundError, TmdbUnavailableError, TmdbRateLimitedError):
                episodes = []
        seasons.append({**season, "owned": owned, "episodes": episodes})
    return seasons


async def preview_from_tmdb(tmdb_id: int) -> TvShowPreview:
    """Feature #79 — samme TMDb-opslag+rating-beregning som `create_tv_show`
    selv bruger, men rent læsende: intet oprettes, og sæsoner udelades
    bevidst (sæson-valget sker allerede i et tidligere trin via den
    eksisterende /tmdb-preview/{id}-sæsonliste, feature #54)."""
    details = await tmdb_client.get_tv_show_details(tmdb_id)
    return TvShowPreview(
        tmdb_id=details["tmdb_id"],
        name=details["name"],
        year=details["year"],
        end_year=details["end_year"],
        status=details["status"],
        poster_url=details["poster_url"],
        overview=details["overview"],
        genres=details["genres"],
        cast=details["cast"],
        creators=details["creators"],
        rating=await _resolve_rating(details),
        number_of_seasons=details["number_of_seasons"],
        number_of_episodes=details["number_of_episodes"],
        imdb_url=details["imdb_url"],
    )


# BUGS.md #62 — se den identiske note i movie_service.
SERIAL_ASSIGN_RETRY_LIMIT = 3


def _is_serial_collision(exc: DuplicateKeyError) -> bool:
    """BUGS.md #62 — se den identiske funktion i movie_service."""
    details = getattr(exc, "details", None) or {}
    key_pattern = details.get("keyPattern") or {}
    if "serial_number" in key_pattern:
        return True
    return "serial_number" in str(exc)


# Feature #139 — se den identiske regel i movie_service (ejere med normal serie
# vs. den delte 5000+-pulje). Bevidst duplikeret her, som resten af serie-logikken
# spejles mellem de to services.
STANDARD_OWNERS = {"jan", "lis", "jan&lis", "lis&jan"}


def _normalize_owner(owner: str | None) -> str:
    return (owner or "").lower().replace(" ", "")


def _uses_other_pool(owner: str | None, creator_is_admin: bool) -> bool:
    """Feature #139 — 5000+-puljen kun når ejeren ikke er en jan/lis-variant OG
    posten ikke er oprettet af en admin. Se movie_service._uses_other_pool."""
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
    oprettet af en admin, får nummer fra den delte 5000+-pulje uanset type.

    `media_type` er påkrævet ved oprettelse af en biblioteks-post, så "ikke
    sat" kan kun forekomme på dokumenter fra før den regel. De får intet
    nummer her; eksisterende dokumenter røres kun af migreringen i
    `digital_serial_repository.backfill`."""
    if is_wishlist:
        return None
    if _uses_other_pool(owner, creator_is_admin):
        return await digital_serial_repository.next_other_serial_number(db)
    if media_type == MediaType.PHYSICAL:
        return await tv_show_repository.next_serial_number(db)
    if media_type == MediaType.DIGITAL:
        return await digital_serial_repository.next_serial_number(db)
    return None


# `creator_is_admin` defaulter til True — se movie_service.create_movie (#139).
async def create_tv_show(
    db: AsyncIOMotorDatabase,
    payload: TvShowCreate,
    registered_by: str,
    creator_is_admin: bool = True,
) -> TvShow:
    canonical_tags = await tag_service.resolve_tags(
        db, [*payload.tags, tag_service.added_by_tag(registered_by)]
    )
    now = datetime.now(timezone.utc)

    if payload.tmdb_id is not None:
        details = await tmdb_client.get_tv_show_details(payload.tmdb_id)
        show_fields = {
            "tmdb_id": details["tmdb_id"],
            "name": details["name"],
            "year": details["year"],
            "end_year": details["end_year"],
            "status": details["status"],
            "poster_url": details["poster_url"],
            "overview": details["overview"],
            "genres": details["genres"],
            "cast": details["cast"],
            "creators": details["creators"],
            "rating": await _resolve_rating(details),
            "number_of_seasons": details["number_of_seasons"],
            "number_of_episodes": details["number_of_episodes"],
            "imdb_url": details["imdb_url"],
            "seasons": await _build_seasons(
                details["tmdb_id"], details["seasons"], payload.owned_seasons
            ),
        }
    else:
        show_fields = {
            "tmdb_id": None,
            "name": payload.name,
            "year": payload.year,
            "end_year": None,
            "status": None,
            "poster_url": payload.poster_url,
            "overview": payload.overview,
            "genres": payload.genres,
            "cast": payload.cast,
            "creators": [],
            "rating": None,
            "number_of_seasons": None,
            "number_of_episodes": None,
            "imdb_url": None,
            "seasons": [],
        }

    document = {
        **show_fields,
        "tags": canonical_tags,
        "tags_normalized": [tag_service.normalize(tag) for tag in canonical_tags],
        "format": payload.format.value if payload.format else None,
        "audio_types": [audio_type.value for audio_type in payload.audio_types],
        "media_type": payload.media_type.value if payload.media_type else None,
        "location": payload.location,
        "owner": payload.owner or registered_by,
        "subtitles": coerce_subtitles(payload.subtitles),
        "order_status": payload.order_status.value if payload.order_status else None,
        "registered_by": registered_by,
        "is_wishlist": payload.is_wishlist,
        # Feature #144 — se den identiske logik i movie_service.create_movie.
        "wishlist_status": (
            (WishlistStatus.APPROVED.value if creator_is_admin else WishlistStatus.PENDING.value)
            if payload.is_wishlist
            else None
        ),
        "created_at": now,
        "updated_at": now,
    }
    # Feature #92 — kun fysiske udgaver nummereres, se den identiske regel og
    # begrundelse i movie_service. TV-serier har sin egen nummer-serie
    # (`tv_show_serial`-tælleren), adskilt fra filmenes.
    trimmed_barcode = payload.barcode.strip() if payload.barcode else ""
    if trimmed_barcode:
        document["barcode"] = trimmed_barcode
    if payload.barcode_source:
        document["barcode_source"] = payload.barcode_source

    # BUGS.md #62 — se den identiske løkke i movie_service.create_movie.
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
            created = await tv_show_repository.insert(db, document)
            return _to_model(created)
        except DuplicateKeyError as exc:
            if _is_serial_collision(exc):
                continue
            raise DuplicateBarcodeError(trimmed_barcode) from exc
    raise SerialNumberConflictError(
        "Kunne ikke finde et ledigt serienummer efter flere forsøg"
    )


def parse_sort_param(sort: str | None) -> list[tuple[str, int]]:
    if not sort:
        return []
    levels: list[tuple[str, int]] = []
    for token in sort.split(",")[: tv_show_repository.MAX_SORT_LEVELS]:
        field, _, direction = token.partition(":")
        keys = tv_show_repository.SORT_FIELDS.get(field)
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
    """Feature #156 — se den identiske funktion i movie_service.py (samme
    begrundelse for det lokale import af `plex_service`)."""
    if plex is None:
        return {}
    from app.services import plex_service

    available_ids = await plex_service.get_available_ids(db, "show")
    if available_ids is None:
        raise PlexFilterUnavailableError()
    return {"id_in": list(available_ids)} if plex else {"id_nin": list(available_ids)}


async def list_tv_shows(
    db: AsyncIOMotorDatabase,
    q: str | None,
    tags: list[str] | None,
    formats: list[str] | None = None,
    audio_types: list[str] | None = None,
    media_types: list[str] | None = None,
    sort: str | None = None,
    is_wishlist: bool = False,
    watched: bool | None = None,
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
) -> TvShowPage:
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
        **(await _resolve_plex_id_filter(db, plex)),
    }

    documents = await tv_show_repository.find_many(db, filters, sort_spec or None, skip, limit)
    # Feature #145 — markér ønsker hvis navnet falder sammen med en titel i
    # biblioteket (TV ELLER film). Se den identiske logik i movie_service.
    if is_wishlist and documents:
        library_titles = await tv_show_repository.library_titles_normalized(db)
        library_titles |= await movie_repository.library_titles_normalized(db)
        for doc in documents:
            name = (doc.get("name") or "").strip().lower()
            doc["name_in_library"] = bool(name) and name in library_titles

    items = [_to_model(doc) for doc in documents]

    if paginating:
        total = await tv_show_repository.count_many(db, filters)
    else:
        total = len(items)

    return TvShowPage(items=items, total=total)


async def list_genres(db: AsyncIOMotorDatabase) -> list[str]:
    """Feature #111 — se den identiske funktion i movie_service.py."""
    return await tv_show_repository.distinct_genres(db)


async def check_tmdb_duplicates(db: AsyncIOMotorDatabase, tmdb_id: int) -> list[DuplicateTvShowMatch]:
    documents = await tv_show_repository.find_by_tmdb_id(db, tmdb_id)
    return [
        DuplicateTvShowMatch(
            id=str(doc["_id"]),
            name=doc["name"],
            serial_number=doc.get("serial_number"),
            is_wishlist=doc.get("is_wishlist", False),
        )
        for doc in documents
    ]


async def get_tv_show(db: AsyncIOMotorDatabase, tv_show_id: str) -> TvShow:
    document = await tv_show_repository.find_by_id(db, tv_show_id)
    if document is None:
        raise TvShowNotFoundError(tv_show_id)
    return _to_model(document)


_TEMP_SERIAL_NUMBER = -1


async def _reassign_serial_number(
    db: AsyncIOMotorDatabase, tv_show_id: str, current_doc: dict, new_serial: int
) -> None:
    """Serie-bevidst byt-plads, se movie_service._reassign_serial_number og
    BUGS.md #56. En fysisk TV-serie bytter kun inden for T#-rækken; en digital
    inden for den delte D#-række, som kan have en digital *film* som holder — så
    swap'et kan skulle skrive i movies-collection."""
    old_serial = current_doc["serial_number"]
    if new_serial == old_serial:
        return

    holder = await digital_serial_repository.find_series_holder(
        db,
        current_doc.get("media_type"),
        new_serial,
        tv_show_repository.COLLECTION,
        current_doc["_id"],
    )
    try:
        if holder is not None:
            collection_name, doc = holder
            await tv_show_repository.set_serial_number(db, tv_show_id, _TEMP_SERIAL_NUMBER)
            await digital_serial_repository.set_serial(
                db, collection_name, doc["_id"], old_serial
            )
        await tv_show_repository.set_serial_number(db, tv_show_id, new_serial)
    except DuplicateKeyError as exc:
        raise SerialNumberConflictError(new_serial) from exc


def _assert_can_edit_serial_number(current_user: dict, tv_show_doc: dict) -> None:
    is_admin = current_user.get("role") == "admin"
    is_registrant = tv_show_doc.get("registered_by") == current_user.get("username")
    if not (is_admin or is_registrant):
        raise NotAuthorizedError(
            "Kun en admin eller den bruger der registrerede TV-serien kan ændre serienummeret"
        )


async def update_tv_show(
    db: AsyncIOMotorDatabase, tv_show_id: str, payload: TvShowUpdate, current_user: dict
) -> TvShow:
    # BUGS.md #59 — bevidst IKKE mode="json" (se den identiske note i
    # movie_service.update_movie): bevarer `watched_at` som ægte datetime.
    fields = payload.model_dump(exclude_unset=True)

    # Feature #144 — kun en admin må godkende et ønske (regel 16).
    if "wishlist_status" in fields and current_user.get("role") != "admin":
        raise NotAuthorizedError("Kun en admin kan godkende ønsker")

    if "tags" in fields:
        canonical_tags = await tag_service.resolve_tags(db, fields["tags"])
        fields["tags"] = canonical_tags
        fields["tags_normalized"] = [tag_service.normalize(tag) for tag in canonical_tags]

    # Feature #123 — samme normalisering som create/movie_service.
    if "subtitles" in fields:
        fields["subtitles"] = coerce_subtitles(fields["subtitles"])

    requested_serial = fields.pop("serial_number", None)
    requested_wishlist = fields.pop("is_wishlist", None)
    requested_media_type = fields.get("media_type")

    current_doc = None
    if (
        requested_serial is not None
        or requested_wishlist is not None
        or requested_media_type is not None
    ):
        current_doc = await tv_show_repository.find_by_id(db, tv_show_id)
        if current_doc is None:
            raise TvShowNotFoundError(tv_show_id)

    # Feature #141 — flyttes et ønske ind i biblioteket, får ønske-opretteren
    # besked efter skrivningen (se movie_service for den identiske logik).
    moved_to_library = False
    if requested_wishlist is not None:
        was_wishlist = current_doc.get("is_wishlist", False)
        fields["is_wishlist"] = requested_wishlist
        media_type = requested_media_type or current_doc.get("media_type")
        if was_wishlist and not requested_wishlist:
            moved_to_library = True
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
            _assert_can_edit_serial_number(current_user, current_doc)
            await tv_show_repository.clear_serial_number(db, tv_show_id)
    elif requested_serial is not None:
        _assert_can_edit_serial_number(current_user, current_doc)
        await _reassign_serial_number(db, tv_show_id, current_doc, requested_serial)
    elif requested_media_type is not None:
        # Feature #92 — reglen håndhæves begge veje, se movie_service.
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
            await tv_show_repository.clear_serial_number(db, tv_show_id)

    fields["updated_at"] = datetime.now(timezone.utc)

    document = await tv_show_repository.update(db, tv_show_id, fields)
    if document is None:
        raise TvShowNotFoundError(tv_show_id)
    if moved_to_library:
        await message_service.notify_wishlist_moved(
            db, current_doc, current_user, document.get("name"), is_tv=True
        )
    return _to_model(document)


async def delete_tv_show(db: AsyncIOMotorDatabase, tv_show_id: str, deleted_by: str) -> None:
    document = await tv_show_repository.find_by_id(db, tv_show_id)
    if document is None:
        raise TvShowNotFoundError(tv_show_id)

    await tv_show_repository.archive_deleted(db, document, deleted_by)
    deleted = await tv_show_repository.delete(db, tv_show_id)
    if not deleted:
        raise TvShowNotFoundError(tv_show_id)

    # BUGS.md #43 — same dangling-reference cleanup as movie deletion; see
    # `movie_service.delete_movie` for why this is necessary.
    await screening_repository.delete_for_title(db, "tv", tv_show_id)
    await screening_request_repository.delete_for_title(db, "tv", tv_show_id)


async def list_deleted_tv_shows(db: AsyncIOMotorDatabase) -> list[DeletedTvShow]:
    documents = await tv_show_repository.list_deleted(db)
    return [
        DeletedTvShow(
            id=str(doc["_id"]),
            serial_number=doc.get("serial_number"),
            name=doc["name"],
            year=doc.get("year"),
            format=doc.get("format"),
            deleted_at=doc["deleted_at"],
            deleted_by=doc.get("deleted_by"),
        )
        for doc in documents
    ]


def _find_season(document: dict, season_number: int) -> dict | None:
    for season in document.get("seasons", []):
        if season["season_number"] == season_number:
            return season
    return None


def _find_season_index(document: dict, season_number: int) -> int | None:
    for index, season in enumerate(document.get("seasons", [])):
        if season["season_number"] == season_number:
            return index
    return None


async def set_season_owned(
    db: AsyncIOMotorDatabase, tv_show_id: str, season_number: int, owned: bool
) -> TvShow:
    """Marking a season as owned lazily fetches and caches its full episode
    list from TMDb the *first* time (if not already cached) — see
    ARCHITECTURE.md's "Lazy sæson/episode-load" note (feature #48).
    Un-marking a season does not clear its cached episodes/watched-status —
    only ownership, so re-marking it owned later doesn't lose watch
    history."""
    document = await tv_show_repository.find_by_id(db, tv_show_id)
    if document is None:
        raise TvShowNotFoundError(tv_show_id)

    season = _find_season(document, season_number)
    if season is None:
        raise TvShowNotFoundError(tv_show_id)

    if owned and not season.get("episodes") and document.get("tmdb_id") is not None:
        raw_episodes = await tmdb_client.get_season_details(document["tmdb_id"], season_number)
        episodes = [
            Episode(episode_number=ep["episode_number"], name=ep["name"], air_date=ep["air_date"]).model_dump(
                mode="json"
            )
            for ep in raw_episodes
        ]
        await tv_show_repository.set_season_episodes(db, tv_show_id, season_number, episodes)

    await tv_show_repository.set_season_owned(db, tv_show_id, season_number, owned)

    updated = await tv_show_repository.find_by_id(db, tv_show_id)
    return _to_model(updated)


async def set_episode_watched(
    db: AsyncIOMotorDatabase,
    tv_show_id: str,
    season_number: int,
    episode_number: int,
    watched: bool,
    watched_at: datetime | None,
) -> TvShow:
    document = await tv_show_repository.find_by_id(db, tv_show_id)
    if document is None:
        raise TvShowNotFoundError(tv_show_id)

    season_index = _find_season_index(document, season_number)
    if season_index is None:
        raise TvShowNotFoundError(tv_show_id)

    episodes = document["seasons"][season_index].get("episodes", [])
    episode_index = next(
        (i for i, ep in enumerate(episodes) if ep["episode_number"] == episode_number), None
    )
    if episode_index is None:
        raise TvShowNotFoundError(tv_show_id)

    # Atomic single-field update, not read-modify-write — see BUGS.md #25.
    await tv_show_repository.set_episode_watched(
        db, tv_show_id, season_index, episode_index, watched, watched_at
    )

    updated = await tv_show_repository.find_by_id(db, tv_show_id)
    return _to_model(updated)


def _merge_seasons(existing_seasons: list[dict], tmdb_seasons: list[dict]) -> list[dict]:
    """Refreshes each season's TMDb-sourced metadata (name/episode_count/
    air_date/poster_url) while preserving `owned` and cached `episodes`
    (with their watched-status) by matching on `season_number` — those are
    the TV show's per-season equivalent of a movie's user-entered fields
    (tags/format/location/...), which `sync_all_from_tmdb` must never touch
    (FEATURES.md #57). A season TMDb no longer lists is dropped; a newly
    announced season is added unowned with no cached episodes yet, same as
    at initial creation."""
    existing_by_number = {season["season_number"]: season for season in existing_seasons}
    merged = []
    for season in tmdb_seasons:
        existing = existing_by_number.get(season["season_number"])
        merged.append(
            {
                **season,
                "owned": existing["owned"] if existing else False,
                "episodes": existing.get("episodes", []) if existing else [],
            }
        )
    return merged


async def sync_all_from_tmdb(db: AsyncIOMotorDatabase) -> TmdbSyncResult:
    """TV-show counterpart to movie_service.sync_all_from_tmdb (FEATURES.md
    #57) — same batch semantics: a missing TMDB_API_TOKEN or a mid-batch
    rate-limit short-circuits the rest of the batch instead of hammering an
    already-unavailable/throttled TMDb per show (see BUGS.md #15/#16), and
    a single show's TMDb lookup failing doesn't abort the rest. Never
    touches user-entered fields (tags/format/location/owner/serial_number/
    registered_by/barcode/personal_rating/personal_note/watched/is_wishlist)
    nor a season's `owned`/episode `watched` status — see `_merge_seasons`."""
    documents = await tv_show_repository.find_all_with_tmdb_id(db)

    if not settings.tmdb_api_token:
        names = [doc["name"] for doc in documents]
        return TmdbSyncResult(
            total=len(documents),
            synced=0,
            failed=len(names),
            failed_titles=names,
            stopped_early=True,
        )

    synced = 0
    failed_titles: list[str] = []
    stopped_early = False

    for index, document in enumerate(documents):
        try:
            details = await tmdb_client.get_tv_show_details(document["tmdb_id"])
        except TmdbRateLimitedError:
            failed_titles.extend(doc["name"] for doc in documents[index:])
            stopped_early = True
            break
        except (TmdbNotFoundError, TmdbUnavailableError):
            failed_titles.append(document["name"])
            continue

        fields = {
            "name": details["name"],
            "year": details["year"],
            "end_year": details["end_year"],
            "status": details["status"],
            "poster_url": details["poster_url"],
            "overview": details["overview"],
            "genres": details["genres"],
            "cast": details["cast"],
            "creators": details["creators"],
            "rating": await _resolve_rating(details),
            "number_of_seasons": details["number_of_seasons"],
            "number_of_episodes": details["number_of_episodes"],
            "imdb_url": details["imdb_url"],
            "seasons": _merge_seasons(document.get("seasons", []), details["seasons"]),
            "updated_at": datetime.now(timezone.utc),
        }
        await tv_show_repository.update(db, str(document["_id"]), fields)
        synced += 1
        await asyncio.sleep(0.05)  # be gentle with TMDb across a large batch

    return TmdbSyncResult(
        total=len(documents),
        synced=synced,
        failed=len(failed_titles),
        failed_titles=failed_titles,
        stopped_early=stopped_early,
    )
