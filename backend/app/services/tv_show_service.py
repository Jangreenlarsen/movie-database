from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.errors import (
    DuplicateBarcodeError,
    NotAuthorizedError,
    TvShowNotFoundError,
)
from app.integrations import omdb_client, tmdb_client
from app.models.tv_show import (
    DeletedTvShow,
    DuplicateTvShowMatch,
    Episode,
    Season,
    TvShow,
    TvShowCreate,
    TvShowUpdate,
)
from app.repositories import tv_show_repository
from app.services import tag_service


def _to_model(document: dict) -> TvShow:
    return TvShow(
        id=str(document["_id"]),
        serial_number=document.get("serial_number"),
        tmdb_id=document.get("tmdb_id"),
        barcode=document.get("barcode"),
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
        registered_by=document.get("registered_by"),
        is_wishlist=document.get("is_wishlist", False),
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


async def create_tv_show(
    db: AsyncIOMotorDatabase, payload: TvShowCreate, registered_by: str
) -> TvShow:
    canonical_tags = await tag_service.resolve_tags(db, payload.tags)
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
            "seasons": [
                {**season, "owned": False, "episodes": []} for season in details["seasons"]
            ],
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
        "registered_by": registered_by,
        "is_wishlist": payload.is_wishlist,
        "created_at": now,
        "updated_at": now,
    }
    if not payload.is_wishlist:
        document["serial_number"] = await tv_show_repository.next_serial_number(db)

    trimmed_barcode = payload.barcode.strip() if payload.barcode else ""
    if trimmed_barcode:
        document["barcode"] = trimmed_barcode

    try:
        created = await tv_show_repository.insert(db, document)
    except DuplicateKeyError as exc:
        raise DuplicateBarcodeError(trimmed_barcode) from exc
    return _to_model(created)


def parse_sort_param(sort: str | None) -> list[tuple[str, int]]:
    if not sort:
        return []
    levels: list[tuple[str, int]] = []
    for token in sort.split(",")[: tv_show_repository.MAX_SORT_LEVELS]:
        field, _, direction = token.partition(":")
        mongo_field = tv_show_repository.SORT_FIELDS.get(field)
        if mongo_field is None:
            continue
        levels.append((mongo_field, -1 if direction == "desc" else 1))
    return levels


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
) -> list[TvShow]:
    normalized_tags = [tag_service.normalize(tag) for tag in (tags or []) if tag.strip()]
    sort_spec = parse_sort_param(sort)
    documents = await tv_show_repository.find_many(
        db,
        q,
        normalized_tags or None,
        formats or None,
        audio_types or None,
        media_types or None,
        sort_spec or None,
        is_wishlist,
        watched,
    )
    return [_to_model(doc) for doc in documents]


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
    old_serial = current_doc["serial_number"]
    if new_serial == old_serial:
        return

    conflicting = await tv_show_repository.find_by_serial_number(db, new_serial)
    if conflicting is not None and conflicting["_id"] != current_doc["_id"]:
        await tv_show_repository.set_serial_number(db, tv_show_id, _TEMP_SERIAL_NUMBER)
        await tv_show_repository.set_serial_number(db, str(conflicting["_id"]), old_serial)

    await tv_show_repository.set_serial_number(db, tv_show_id, new_serial)


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
    fields = payload.model_dump(exclude_unset=True, mode="json")

    if "tags" in fields:
        canonical_tags = await tag_service.resolve_tags(db, fields["tags"])
        fields["tags"] = canonical_tags
        fields["tags_normalized"] = [tag_service.normalize(tag) for tag in canonical_tags]

    requested_serial = fields.pop("serial_number", None)
    requested_wishlist = fields.pop("is_wishlist", None)

    current_doc = None
    if requested_serial is not None or requested_wishlist is not None:
        current_doc = await tv_show_repository.find_by_id(db, tv_show_id)
        if current_doc is None:
            raise TvShowNotFoundError(tv_show_id)

    if requested_wishlist is not None:
        was_wishlist = current_doc.get("is_wishlist", False)
        fields["is_wishlist"] = requested_wishlist
        if was_wishlist and not requested_wishlist:
            fields["serial_number"] = await tv_show_repository.next_serial_number(db)
        elif not was_wishlist and requested_wishlist:
            _assert_can_edit_serial_number(current_user, current_doc)
            await tv_show_repository.clear_serial_number(db, tv_show_id)
    elif requested_serial is not None:
        _assert_can_edit_serial_number(current_user, current_doc)
        await _reassign_serial_number(db, tv_show_id, current_doc, requested_serial)

    fields["updated_at"] = datetime.now(timezone.utc)

    document = await tv_show_repository.update(db, tv_show_id, fields)
    if document is None:
        raise TvShowNotFoundError(tv_show_id)
    return _to_model(document)


async def delete_tv_show(db: AsyncIOMotorDatabase, tv_show_id: str, deleted_by: str) -> None:
    document = await tv_show_repository.find_by_id(db, tv_show_id)
    if document is None:
        raise TvShowNotFoundError(tv_show_id)

    await tv_show_repository.archive_deleted(db, document, deleted_by)
    deleted = await tv_show_repository.delete(db, tv_show_id)
    if not deleted:
        raise TvShowNotFoundError(tv_show_id)


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

    season = _find_season(document, season_number)
    if season is None:
        raise TvShowNotFoundError(tv_show_id)

    episodes = season.get("episodes", [])
    found = False
    for episode in episodes:
        if episode["episode_number"] == episode_number:
            episode["watched"] = watched
            episode["watched_at"] = watched_at
            found = True
            break
    if not found:
        raise TvShowNotFoundError(tv_show_id)

    await tv_show_repository.set_season_episodes(db, tv_show_id, season_number, episodes)

    updated = await tv_show_repository.find_by_id(db, tv_show_id)
    return _to_model(updated)
