from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.errors import DuplicateBarcodeError, MovieNotFoundError
from app.integrations import tmdb_client
from app.models.movie import Movie, MovieCreate, MovieUpdate
from app.repositories import movie_repository
from app.services import tag_service


def _to_model(document: dict) -> Movie:
    return Movie(
        id=str(document["_id"]),
        tmdb_id=document.get("tmdb_id"),
        barcode=document.get("barcode"),
        title=document["title"],
        year=document.get("year"),
        poster_url=document.get("poster_url"),
        overview=document.get("overview"),
        genres=document.get("genres", []),
        cast=document.get("cast", []),
        tags=document.get("tags", []),
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


async def create_movie(db: AsyncIOMotorDatabase, payload: MovieCreate) -> Movie:
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
        }

    document = {
        **movie_fields,
        "barcode": payload.barcode,
        "tags": canonical_tags,
        "tags_normalized": [tag_service.normalize(tag) for tag in canonical_tags],
        "created_at": now,
        "updated_at": now,
    }
    try:
        created = await movie_repository.insert(db, document)
    except DuplicateKeyError as exc:
        raise DuplicateBarcodeError(payload.barcode or "") from exc
    return _to_model(created)


async def list_movies(
    db: AsyncIOMotorDatabase, q: str | None, tags: list[str] | None
) -> list[Movie]:
    normalized_tags = [tag_service.normalize(tag) for tag in (tags or []) if tag.strip()]
    documents = await movie_repository.find_many(db, q, normalized_tags or None)
    return [_to_model(doc) for doc in documents]


async def get_movie(db: AsyncIOMotorDatabase, movie_id: str) -> Movie:
    document = await movie_repository.find_by_id(db, movie_id)
    if document is None:
        raise MovieNotFoundError(movie_id)
    return _to_model(document)


async def update_movie(db: AsyncIOMotorDatabase, movie_id: str, payload: MovieUpdate) -> Movie:
    fields = payload.model_dump(exclude_unset=True)

    if "tags" in fields:
        canonical_tags = await tag_service.resolve_tags(db, fields["tags"])
        fields["tags"] = canonical_tags
        fields["tags_normalized"] = [tag_service.normalize(tag) for tag in canonical_tags]

    fields["updated_at"] = datetime.now(timezone.utc)

    document = await movie_repository.update(db, movie_id, fields)
    if document is None:
        raise MovieNotFoundError(movie_id)
    return _to_model(document)


async def delete_movie(db: AsyncIOMotorDatabase, movie_id: str) -> None:
    deleted = await movie_repository.delete(db, movie_id)
    if not deleted:
        raise MovieNotFoundError(movie_id)
