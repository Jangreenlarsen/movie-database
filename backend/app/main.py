import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, health, movies, scan, settings as settings_api, system, tags, users
from app.core.config import settings
from app.core.errors import (
    DeployScriptNotFoundError,
    DuplicateBarcodeError,
    InvalidCredentialsError,
    LastAdminError,
    MovieNotFoundError,
    NotAuthenticatedError,
    NotAuthorizedError,
    TmdbNotFoundError,
    TmdbUnavailableError,
    UserNotFoundError,
    UsernameTakenError,
)
from app.db import close_client, get_client, get_database
from app.repositories import movie_repository, tag_repository, user_repository
from app.services import system_settings_service

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("moviedb")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.using_insecure_jwt_secret:
        logger.warning(
            "JWT_SECRET_KEY er ikke sat — bruger den usikre standard-vaerdi. "
            "Saet en unik hemmelighed i .env foer denne app naar udenfor lokal udvikling "
            "(python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
        )

    get_client()
    db = get_database()
    await system_settings_service.apply_overrides_on_startup(db)
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


@app.exception_handler(NotAuthorizedError)
async def not_authorized_handler(request: Request, exc: NotAuthorizedError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request: Request, exc: UserNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(LastAdminError)
async def last_admin_handler(request: Request, exc: LastAdminError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DeployScriptNotFoundError)
async def deploy_script_not_found_handler(
    request: Request, exc: DeployScriptNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(movies.router)
app.include_router(tags.router)
app.include_router(scan.router)
app.include_router(settings_api.router)
app.include_router(system.router)
