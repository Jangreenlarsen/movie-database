from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_database
from app.models.movie import Movie, MovieCreate, MovieUpdate
from app.services import movie_service

router = APIRouter(prefix="/api/movies", tags=["movies"])


@router.get("", response_model=list[Movie])
async def list_movies(
    q: str | None = Query(default=None),
    tags: str | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    tag_list = tags.split(",") if tags else None
    return await movie_service.list_movies(db, q, tag_list)


@router.post("", response_model=Movie, status_code=201)
async def create_movie(payload: MovieCreate, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await movie_service.create_movie(db, payload)


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
