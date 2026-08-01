from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.errors import DuplicateBarcodeError, MovieNotFoundError, NotAuthorizedError
from app.integrations import tmdb_client
from app.models.movie import DeletedMovie, Movie, MovieCreate, MovieUpdate
from app.models.settings import SerialNumberConfig, SerialNumberConfigUpdate
from app.repositories import movie_repository
from app.services import tag_service


def _to_model(document: dict) -> Movie:
    return Movie(
        id=str(document["_id"]),
        serial_number=document["serial_number"],
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
        rating=document.get("rating"),
        runtime=document.get("runtime"),
        location=document.get("location"),
        owner=document.get("owner"),
        registered_by=document.get("registered_by"),
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
        }

    serial_number = await movie_repository.next_serial_number(db)

    document = {
        **movie_fields,
        "serial_number": serial_number,
        "tags": canonical_tags,
        "tags_normalized": [tag_service.normalize(tag) for tag in canonical_tags],
        "format": payload.format.value if payload.format else None,
        "audio_types": [audio_type.value for audio_type in payload.audio_types],
        "location": payload.location,
        "owner": payload.owner or registered_by,
        "registered_by": registered_by,
        "created_at": now,
        "updated_at": now,
    }
    trimmed_barcode = payload.barcode.strip() if payload.barcode else ""
    if trimmed_barcode:
        document["barcode"] = trimmed_barcode

    try:
        created = await movie_repository.insert(db, document)
    except DuplicateKeyError as exc:
        raise DuplicateBarcodeError(trimmed_barcode) from exc
    return _to_model(created)


async def list_movies(
    db: AsyncIOMotorDatabase,
    q: str | None,
    tags: list[str] | None,
    formats: list[str] | None = None,
    audio_types: list[str] | None = None,
    sort: str | None = None,
    direction: str | None = None,
) -> list[Movie]:
    normalized_tags = [tag_service.normalize(tag) for tag in (tags or []) if tag.strip()]
    sort_direction = 1 if direction == "asc" else -1
    documents = await movie_repository.find_many(
        db, q, normalized_tags or None, formats or None, audio_types or None, sort, sort_direction
    )
    return [_to_model(doc) for doc in documents]


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
    if requested_serial is not None:
        current_doc = await movie_repository.find_by_id(db, movie_id)
        if current_doc is None:
            raise MovieNotFoundError(movie_id)
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


async def get_serial_number_config(db: AsyncIOMotorDatabase) -> SerialNumberConfig:
    config = await movie_repository.get_serial_config(db)
    return SerialNumberConfig(**config)


async def update_serial_number_config(
    db: AsyncIOMotorDatabase, payload: SerialNumberConfigUpdate
) -> SerialNumberConfig:
    updates = payload.model_dump(exclude_unset=True)
    config = await movie_repository.update_serial_config(db, updates)
    return SerialNumberConfig(**config)
