from typing import Literal

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_database
from app.integrations import tmdb_client
from app.models.movie import AudioType, Movie, MovieCreate, MovieFormat, MovieUpdate
from app.models.scan import MovieCandidate
from app.services import movie_service

router = APIRouter(prefix="/api/movies", tags=["movies"])


@router.get("", response_model=list[Movie])
async def list_movies(
    q: str | None = Query(default=None),
    tags: str | None = Query(default=None),
    format: str | None = Query(default=None, alias="format"),
    audio_types: str | None = Query(default=None),
    sort: Literal["title", "year", "serial_number", "rating"] | None = Query(default=None),
    direction: Literal["asc", "desc"] | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    tag_list = tags.split(",") if tags else None
    format_list = format.split(",") if format else None
    audio_type_list = audio_types.split(",") if audio_types else None
    return await movie_service.list_movies(
        db, q, tag_list, format_list, audio_type_list, sort, direction
    )


@router.post("", response_model=Movie, status_code=201)
async def create_movie(payload: MovieCreate, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await movie_service.create_movie(db, payload)


# NOTE: must be registered before GET /{movie_id} — otherwise these literal
# paths match the {movie_id} path parameter instead.
@router.get("/tmdb-search", response_model=list[MovieCandidate])
async def tmdb_search(query: str = Query(...)):
    candidates = await tmdb_client.search_movies(query)
    return [MovieCandidate(**candidate) for candidate in candidates]


@router.get("/attribute-options")
async def attribute_options() -> dict:
    return {
        "formats": [f.value for f in MovieFormat],
        "audio_types": [a.value for a in AudioType],
    }


@router.get("/{movie_id}", response_model=Movie)
async def get_movie(movie_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await movie_service.get_movie(db, movie_id)


@router.patch("/{movie_id}", response_model=Movie)
async def update_movie(
    movie_id: str, payload: MovieUpdate, db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await movie_service.update_movie(db, movie_id, payload)


@router.delete("/{movie_id}", status_code=204)
async def delete_movie(movie_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    await movie_service.delete_movie(db, movie_id)
