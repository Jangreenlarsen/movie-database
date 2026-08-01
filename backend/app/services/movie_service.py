import asyncio
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.errors import (
    DuplicateBarcodeError,
    MovieNotFoundError,
    NotAuthorizedError,
    TmdbNotFoundError,
    TmdbRateLimitedError,
    TmdbUnavailableError,
)
from app.integrations import tmdb_client
from app.models.movie import (
    DeletedMovie,
    DuplicateMatch,
    Movie,
    MovieCreate,
    MovieUpdate,
    TmdbSyncResult,
)
from app.models.settings import SerialNumberConfig, SerialNumberConfigUpdate
from app.repositories import movie_repository
from app.services import tag_service


def _to_model(document: dict) -> Movie:
    return Movie(
        id=str(document["_id"]),
        serial_number=document.get("serial_number"),
        tmdb_id=document.get("tmdb_id"),
        barcode=document.get("barcode"),
        title=document["title"],
        year=document.get("year"),
        poster_url=document.get("poster_url"),
        overview=document.get("overview"),
        genres=document.get("genres", []),
        cast=document.get("cast", []),
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
        registered_by=document.get("registered_by"),
        is_wishlist=document.get("is_wishlist", False),
        personal_rating=document.get("personal_rating"),
        personal_note=document.get("personal_note"),
        watched=document.get("watched", False),
        watched_at=document.get("watched_at"),
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


async def create_movie(db: AsyncIOMotorDatabase, payload: MovieCreate, registered_by: str) -> Movie:
    canonical_tags = await tag_service.resolve_tags(db, payload.tags)
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
            "rating": details["rating"],
            "runtime": details["runtime"],
            "imdb_url": details["imdb_url"],
            "trailer_url": details["trailer_url"],
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
            "rating": None,
            "runtime": payload.runtime,
            "imdb_url": payload.imdb_url,
            "trailer_url": payload.trailer_url,
        }

    document = {
        **movie_fields,
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
    # Wishlist items aren't part of the numbered physical collection — omit
    # the key entirely (same "absent, not null" pattern as `barcode`, see
    # BUGS.md #1/#10) so the sparse unique index on `serial_number` never
    # sees a collision between two wishlist items.
    if not payload.is_wishlist:
        document["serial_number"] = await movie_repository.next_serial_number(db)

    trimmed_barcode = payload.barcode.strip() if payload.barcode else ""
    if trimmed_barcode:
        document["barcode"] = trimmed_barcode

    try:
        created = await movie_repository.insert(db, document)
    except DuplicateKeyError as exc:
        raise DuplicateBarcodeError(trimmed_barcode) from exc
    return _to_model(created)


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
        mongo_field = movie_repository.SORT_FIELDS.get(field)
        if mongo_field is None:
            continue
        levels.append((mongo_field, -1 if direction == "desc" else 1))
    return levels


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
) -> list[Movie]:
    normalized_tags = [tag_service.normalize(tag) for tag in (tags or []) if tag.strip()]
    sort_spec = parse_sort_param(sort)
    documents = await movie_repository.find_many(
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


async def check_tmdb_duplicates(db: AsyncIOMotorDatabase, tmdb_id: int) -> list[DuplicateMatch]:
    documents = await movie_repository.find_by_tmdb_id(db, tmdb_id)
    return [
        DuplicateMatch(
            id=str(doc["_id"]),
            title=doc["title"],
            serial_number=doc.get("serial_number"),
            is_wishlist=doc.get("is_wishlist", False),
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
    """Swap with whichever movie currently holds `new_serial`, if any — serial
    numbers are unique, so a direct move would otherwise raise a duplicate-key
    error. See BUGS.md / FEATURES.md #16 for why this trades a hop through a
    sentinel value instead of a single atomic update (Mongo has no built-in
    "swap two unique values" operation without transactions)."""
    old_serial = current_doc["serial_number"]
    if new_serial == old_serial:
        return

    conflicting = await movie_repository.find_by_serial_number(db, new_serial)
    if conflicting is not None and conflicting["_id"] != current_doc["_id"]:
        await movie_repository.set_serial_number(db, movie_id, _TEMP_SERIAL_NUMBER)
        await movie_repository.set_serial_number(db, str(conflicting["_id"]), old_serial)

    await movie_repository.set_serial_number(db, movie_id, new_serial)


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
    fields = payload.model_dump(exclude_unset=True, mode="json")

    if "tags" in fields:
        canonical_tags = await tag_service.resolve_tags(db, fields["tags"])
        fields["tags"] = canonical_tags
        fields["tags_normalized"] = [tag_service.normalize(tag) for tag in canonical_tags]

    requested_serial = fields.pop("serial_number", None)
    requested_wishlist = fields.pop("is_wishlist", None)

    current_doc = None
    if requested_serial is not None or requested_wishlist is not None:
        current_doc = await movie_repository.find_by_id(db, movie_id)
        if current_doc is None:
            raise MovieNotFoundError(movie_id)

    if requested_wishlist is not None:
        was_wishlist = current_doc.get("is_wishlist", False)
        fields["is_wishlist"] = requested_wishlist
        if was_wishlist and not requested_wishlist:
            # Moving from the wishlist into the real collection (feature
            # #28/#32) — assign a fresh serial number, same as at creation.
            # Unrestricted, like POST /api/movies: this isn't "editing" an
            # existing number, it's assigning the first one.
            fields["serial_number"] = await movie_repository.next_serial_number(db)
        elif not was_wishlist and requested_wishlist:
            # The reverse direction strips an existing serial number, which
            # is at least as sensitive as changing one — same gate applies.
            _assert_can_edit_serial_number(current_user, current_doc)
            await movie_repository.clear_serial_number(db, movie_id)
    elif requested_serial is not None:
        _assert_can_edit_serial_number(current_user, current_doc)
        await _reassign_serial_number(db, movie_id, current_doc, requested_serial)

    fields["updated_at"] = datetime.now(timezone.utc)

    document = await movie_repository.update(db, movie_id, fields)
    if document is None:
        raise MovieNotFoundError(movie_id)
    return _to_model(document)


async def delete_movie(db: AsyncIOMotorDatabase, movie_id: str, deleted_by: str) -> None:
    document = await movie_repository.find_by_id(db, movie_id)
    if document is None:
        raise MovieNotFoundError(movie_id)

    await movie_repository.archive_deleted(db, document, deleted_by)
    deleted = await movie_repository.delete(db, movie_id)
    if not deleted:
        raise MovieNotFoundError(movie_id)


async def list_deleted_movies(db: AsyncIOMotorDatabase) -> list[DeletedMovie]:
    documents = await movie_repository.list_deleted(db)
    return [
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
    ]


async def sync_all_from_tmdb(db: AsyncIOMotorDatabase) -> TmdbSyncResult:
    """Re-fetches every TMDb-sourced movie's cached metadata (title, year,
    poster, overview, genres, cast, rating, runtime, IMDb/trailer links) from
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
            "rating": details["rating"],
            "runtime": details["runtime"],
            "imdb_url": details["imdb_url"],
            "trailer_url": details["trailer_url"],
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


async def get_serial_number_config(db: AsyncIOMotorDatabase) -> SerialNumberConfig:
    config = await movie_repository.get_serial_config(db)
    return SerialNumberConfig(**config)


async def update_serial_number_config(
    db: AsyncIOMotorDatabase, payload: SerialNumberConfigUpdate
) -> SerialNumberConfig:
    updates = payload.model_dump(exclude_unset=True)
    config = await movie_repository.update_serial_config(db, updates)
    return SerialNumberConfig(**config)
