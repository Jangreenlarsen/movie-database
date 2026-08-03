from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import ScreeningNotFoundError, ScreeningRequestNotFoundError
from app.models.screening import (
    Screening,
    ScreeningCreate,
    ScreeningRequest,
    ScreeningUpdate,
)
from app.repositories import movie_repository, screening_repository, screening_request_repository, tv_show_repository


async def _resolve_display_info(
    db: AsyncIOMotorDatabase, media_kind: str, movie_id: str | None, tv_show_id: str | None
) -> dict:
    """Looks up title/poster/plot/trailer from the referenced movie/TV
    document — resolved at read-time rather than duplicated onto the
    request/screening document, so the Voldby BIO pages always reflect the
    library's current data (e.g. after a TMDb sync updates a poster)."""
    if media_kind == "movie":
        doc = await movie_repository.find_by_id(db, movie_id) if movie_id else None
        if doc is None:
            return {}
        return {
            "title": doc.get("title"),
            "year": doc.get("year"),
            "poster_url": doc.get("poster_url"),
            "overview": doc.get("overview"),
            "trailer_url": doc.get("trailer_url"),
            "imdb_url": doc.get("imdb_url"),
            "genres": doc.get("genres", []),
            "rating": doc.get("rating"),
        }

    doc = await tv_show_repository.find_by_id(db, tv_show_id) if tv_show_id else None
    if doc is None:
        return {}
    return {
        "title": doc.get("name"),
        "year": doc.get("year"),
        "poster_url": doc.get("poster_url"),
        "overview": doc.get("overview"),
        "trailer_url": None,  # TV shows have no trailer_url field (yet)
        "imdb_url": doc.get("imdb_url"),
        "genres": doc.get("genres", []),
        "rating": doc.get("rating"),
    }


async def _to_request_model(db: AsyncIOMotorDatabase, document: dict) -> ScreeningRequest:
    display = await _resolve_display_info(
        db, document["media_kind"], document.get("movie_id"), document.get("tv_show_id")
    )
    return ScreeningRequest(
        id=str(document["_id"]),
        media_kind=document["media_kind"],
        movie_id=document.get("movie_id"),
        tv_show_id=document.get("tv_show_id"),
        status=document["status"],
        requested_by=document.get("requested_by", []),
        created_at=document["created_at"],
        updated_at=document["updated_at"],
        title=display.get("title"),
        year=display.get("year"),
        poster_url=display.get("poster_url"),
    )


async def _to_screening_model(db: AsyncIOMotorDatabase, document: dict) -> Screening:
    display = await _resolve_display_info(
        db, document["media_kind"], document.get("movie_id"), document.get("tv_show_id")
    )
    return Screening(
        id=str(document["_id"]),
        media_kind=document["media_kind"],
        movie_id=document.get("movie_id"),
        tv_show_id=document.get("tv_show_id"),
        scheduled_at=document["scheduled_at"],
        note=document.get("note"),
        created_by=document["created_by"],
        created_at=document["created_at"],
        **display,
    )


async def request_screening(
    db: AsyncIOMotorDatabase, media_kind: str, movie_id: str | None, tv_show_id: str | None, username: str
) -> ScreeningRequest:
    """Adds `username` to the shared pending request for this title,
    creating the request if none exists yet (feature #62). Re-requesting a
    title you've already requested is a no-op, not a duplicate entry."""
    now = datetime.now(timezone.utc)
    existing = await screening_request_repository.find_pending_for_title(
        db, media_kind, movie_id, tv_show_id
    )
    if existing is None:
        document = {
            "media_kind": media_kind,
            "movie_id": movie_id,
            "tv_show_id": tv_show_id,
            "status": "pending",
            "requested_by": [{"username": username, "requested_at": now}],
            "created_at": now,
            "updated_at": now,
        }
        created = await screening_request_repository.insert(db, document)
        return await _to_request_model(db, created)

    updated = await screening_request_repository.add_requester(
        db, str(existing["_id"]), {"username": username, "requested_at": now}
    )
    return await _to_request_model(db, updated)


async def list_requests(db: AsyncIOMotorDatabase, status: str | None = None) -> list[ScreeningRequest]:
    documents = await screening_request_repository.find_all(db, status)
    return [await _to_request_model(db, doc) for doc in documents]


async def list_my_requests(db: AsyncIOMotorDatabase, username: str) -> list[ScreeningRequest]:
    documents = await screening_request_repository.find_pending_for_user(db, username)
    return [await _to_request_model(db, doc) for doc in documents]


async def decline_request(db: AsyncIOMotorDatabase, request_id: str) -> ScreeningRequest:
    existing = await screening_request_repository.find_by_id(db, request_id)
    if existing is None:
        raise ScreeningRequestNotFoundError(request_id)
    updated = await screening_request_repository.set_status(
        db, request_id, "declined", datetime.now(timezone.utc)
    )
    return await _to_request_model(db, updated)


async def create_screening(
    db: AsyncIOMotorDatabase, payload: ScreeningCreate, created_by: str
) -> Screening:
    now = datetime.now(timezone.utc)
    document = {
        "media_kind": payload.media_kind,
        "movie_id": payload.movie_id,
        "tv_show_id": payload.tv_show_id,
        "scheduled_at": payload.scheduled_at,
        "note": payload.note,
        "created_by": created_by,
        "created_at": now,
    }
    created = await screening_repository.insert(db, document)

    if payload.request_id:
        existing = await screening_request_repository.find_by_id(db, payload.request_id)
        if existing is None:
            raise ScreeningRequestNotFoundError(payload.request_id)
        await screening_request_repository.set_status(db, payload.request_id, "scheduled", now)

    return await _to_screening_model(db, created)


async def list_screenings(db: AsyncIOMotorDatabase, upcoming_only: bool = False) -> list[Screening]:
    documents = await screening_repository.find_all(db, upcoming_only)
    return [await _to_screening_model(db, doc) for doc in documents]


async def update_screening(
    db: AsyncIOMotorDatabase, screening_id: str, payload: ScreeningUpdate
) -> Screening:
    # Deliberately NOT mode="json" — that stringifies `scheduled_at` (a
    # real `datetime`) into ISO text before the raw `$set`, corrupting its
    # BSON type in MongoDB. `find_all`'s `upcoming_only` filter compares
    # `scheduled_at` against a real `datetime` via `$gte`; a string value
    # never matches a date-typed comparison, so an edited screening would
    # silently vanish from the Voldby BIO front page (BUGS.md #33).
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        existing = await screening_repository.find_by_id(db, screening_id)
        if existing is None:
            raise ScreeningNotFoundError(screening_id)
        return await _to_screening_model(db, existing)

    updated = await screening_repository.update(db, screening_id, fields)
    if updated is None:
        raise ScreeningNotFoundError(screening_id)
    return await _to_screening_model(db, updated)


async def delete_screening(db: AsyncIOMotorDatabase, screening_id: str) -> None:
    deleted = await screening_repository.delete(db, screening_id)
    if not deleted:
        raise ScreeningNotFoundError(screening_id)
