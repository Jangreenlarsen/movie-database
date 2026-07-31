import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, health, movies, scan, tags, users
from app.core.config import settings
from app.core.errors import (
    DuplicateBarcodeError,
    InvalidCredentialsError,
    MovieNotFoundError,
    NotAuthenticatedError,
    TmdbNotFoundError,
    TmdbUnavailableError,
    UsernameTakenError,
)
from app.db import close_client, get_client, get_database
from app.repositories import movie_repository, tag_repository, user_repository

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("moviedb")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_client()
    db = get_database()
    await movie_repository.ensure_indexes(db)
    await tag_repository.ensure_indexes(db)
    await user_repository.ensure_indexes(db)
    logger.info("MongoDB client initialized (%s)", settings.mongo_db_name)
    yield
    await close_client()


app = FastAPI(title="Movie Database API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(MovieNotFoundError)
async def movie_not_found_handler(request: Request, exc: MovieNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DuplicateBarcodeError)
async def duplicate_barcode_handler(request: Request, exc: DuplicateBarcodeError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(TmdbNotFoundError)
async def tmdb_not_found_handler(request: Request, exc: TmdbNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(TmdbUnavailableError)
async def tmdb_unavailable_handler(request: Request, exc: TmdbUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(UsernameTakenError)
async def username_taken_handler(request: Request, exc: UsernameTakenError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidCredentialsError)
async def invalid_credentials_handler(
    request: Request, exc: InvalidCredentialsError
) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(NotAuthenticatedError)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(movies.router)
app.include_router(tags.router)
app.include_router(scan.router)
