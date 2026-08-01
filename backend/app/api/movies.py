from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.integrations import tmdb_client
from app.models.movie import (
    AudioType,
    CollectionInfo,
    CollectionStats,
    DeletedMovie,
    DuplicateMatch,
    MediaType,
    Movie,
    MovieCreate,
    MovieFormat,
    MovieUpdate,
    TmdbSyncResult,
)
from app.models.plex import PlexAvailability
from app.models.scan import MovieCandidate
from app.services import movie_service, plex_service

router = APIRouter(prefix="/api/movies", tags=["movies"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[Movie])
async def list_movies(
    q: str | None = Query(default=None),
    tags: str | None = Query(default=None),
    format: str | None = Query(default=None, alias="format"),
    audio_types: str | None = Query(default=None),
    media_types: str | None = Query(default=None),
    sort: str | None = Query(
        default=None,
        description='Comma-separated "field:direction" tokens, up to 3, '
        'e.g. "format:asc,audio_types:asc,title:asc". Unknown fields are '
        "ignored; see movie_repository.SORT_FIELDS for the whitelist.",
    ),
    wishlist: bool = Query(
        default=False, description="True lists the wishlist instead of the main library."
    ),
    watched: bool | None = Query(default=None),
    cast: str | None = Query(default=None, description="Exact cast-member name match."),
    director: str | None = Query(default=None, description="Exact director name match."),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    tag_list = tags.split(",") if tags else None
    format_list = format.split(",") if format else None
    audio_type_list = audio_types.split(",") if audio_types else None
    media_type_list = media_types.split(",") if media_types else None
    return await movie_service.list_movies(
        db,
        q,
        tag_list,
        format_list,
        audio_type_list,
        media_type_list,
        sort,
        wishlist,
        watched,
        cast,
        director,
    )


@router.post("", response_model=Movie, status_code=201)
async def create_movie(
    payload: MovieCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await movie_service.create_movie(db, payload, current_user["username"])


# NOTE: must be registered before GET /{movie_id} — otherwise these literal
# paths match the {movie_id} path parameter instead.
@router.get("/tmdb-search", response_model=list[MovieCandidate])
async def tmdb_search(query: str = Query(...)):
    candidates = await tmdb_client.search_movies(query)
    return [MovieCandidate(**candidate) for candidate in candidates]


@router.get("/check-duplicate", response_model=list[DuplicateMatch])
async def check_duplicate(
    tmdb_id: int = Query(...), db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await movie_service.check_tmdb_duplicates(db, tmdb_id)


@router.get("/stats", response_model=CollectionStats)
async def get_stats(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await movie_service.get_collection_stats(db)


@router.get("/collections/{collection_id}", response_model=CollectionInfo)
async def get_collection(
    collection_id: int, db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await movie_service.get_collection_info(db, collection_id)


@router.get("/attribute-options")
async def attribute_options() -> dict:
    return {
        "formats": [f.value for f in MovieFormat],
        "audio_types": [a.value for a in AudioType],
        "media_types": [m.value for m in MediaType],
    }


@router.get("/deleted", response_model=list[DeletedMovie])
async def list_deleted_movies(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await movie_service.list_deleted_movies(db)


@router.post(
    "/sync-tmdb", response_model=TmdbSyncResult, dependencies=[Depends(require_admin)]
)
async def sync_movies_from_tmdb(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await movie_service.sync_all_from_tmdb(db)


@router.get("/{movie_id}", response_model=Movie)
async def get_movie(movie_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await movie_service.get_movie(db, movie_id)


@router.get("/{movie_id}/plex", response_model=PlexAvailability)
async def get_plex_availability(movie_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    movie = await movie_service.get_movie(db, movie_id)
    return await plex_service.check_availability(movie.tmdb_id, movie.title, movie.year)


@router.patch("/{movie_id}", response_model=Movie)
async def update_movie(
    movie_id: str,
    payload: MovieUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await movie_service.update_movie(db, movie_id, payload, current_user)


@router.delete("/{movie_id}", status_code=204)
async def delete_movie(
    movie_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await movie_service.delete_movie(db, movie_id, current_user["username"])
