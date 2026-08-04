from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin, require_not_guest
from app.db import get_database
from app.integrations import tmdb_client
from app.models.movie import AudioType, MediaType, MovieFormat, TmdbSyncResult
from app.models.scan import MovieCandidate
from app.models.tv_show import (
    DeletedTvShow,
    DuplicateTvShowMatch,
    EpisodeWatchedUpdate,
    Season,
    SeasonOwnedUpdate,
    TvShow,
    TvShowCreate,
    TvShowPage,
    TvShowPreview,
    TvShowUpdate,
)
from app.services import tv_show_service

router = APIRouter(
    prefix="/api/tv-shows", tags=["tv-shows"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=TvShowPage)
async def list_tv_shows(
    q: str | None = Query(default=None),
    tags: str | None = Query(default=None),
    format: str | None = Query(default=None, alias="format"),
    audio_types: str | None = Query(default=None),
    media_types: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    wishlist: bool = Query(default=False),
    watched: bool | None = Query(default=None),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    tag_list = tags.split(",") if tags else None
    format_list = format.split(",") if format else None
    audio_type_list = audio_types.split(",") if audio_types else None
    media_type_list = media_types.split(",") if media_types else None
    return await tv_show_service.list_tv_shows(
        db, q, tag_list, format_list, audio_type_list, media_type_list, sort, wishlist, watched,
        page, page_size,
    )


@router.post("", response_model=TvShow, status_code=201)
async def create_tv_show(
    payload: TvShowCreate,
    current_user: dict = Depends(require_not_guest),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await tv_show_service.create_tv_show(db, payload, current_user["username"])


# NOTE: must be registered before GET /{tv_show_id} — see movies.py for the
# same convention.
@router.get("/tmdb-search", response_model=list[MovieCandidate])
async def tmdb_search(query: str = Query(...)):
    candidates = await tmdb_client.search_tv(query)
    return [MovieCandidate(**candidate, media_kind="tv") for candidate in candidates]


@router.get("/tmdb-preview/{tmdb_id}", response_model=list[Season])
async def tmdb_preview(tmdb_id: int):
    """Let's the add-form show a season picker *before* the show is saved
    (feature #54) — fetches TMDb's light season list without persisting
    anything, same shape `create_tv_show` already builds `seasons[]` from."""
    details = await tmdb_client.get_tv_show_details(tmdb_id)
    return [Season(**season) for season in details["seasons"]]


@router.get("/tmdb-full-preview/{tmdb_id}", response_model=TvShowPreview)
async def tmdb_full_preview(tmdb_id: int):
    """Feature #79 — fuld, rent læsende TMDb-forhåndsvisning af en kandidat
    (samme detalje-niveau som en oprettet serie ville have, minus sæsoner —
    de forhåndsvises stadig separat af `tmdb_preview` ovenfor), til at vise
    rediger-boksen i "kladde"-tilstand før noget er oprettet."""
    return await tv_show_service.preview_from_tmdb(tmdb_id)


@router.get("/check-duplicate", response_model=list[DuplicateTvShowMatch])
async def check_duplicate(
    tmdb_id: int = Query(...), db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await tv_show_service.check_tmdb_duplicates(db, tmdb_id)


@router.get("/attribute-options")
async def attribute_options() -> dict:
    return {
        "formats": [f.value for f in MovieFormat],
        "audio_types": [a.value for a in AudioType],
        "media_types": [m.value for m in MediaType],
    }


@router.get("/deleted", response_model=list[DeletedTvShow])
async def list_deleted_tv_shows(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await tv_show_service.list_deleted_tv_shows(db)


@router.post(
    "/sync-tmdb", response_model=TmdbSyncResult, dependencies=[Depends(require_admin)]
)
async def sync_tv_shows_from_tmdb(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await tv_show_service.sync_all_from_tmdb(db)


@router.get("/{tv_show_id}", response_model=TvShow)
async def get_tv_show(tv_show_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await tv_show_service.get_tv_show(db, tv_show_id)


@router.patch("/{tv_show_id}", response_model=TvShow)
async def update_tv_show(
    tv_show_id: str,
    payload: TvShowUpdate,
    current_user: dict = Depends(require_not_guest),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await tv_show_service.update_tv_show(db, tv_show_id, payload, current_user)


@router.delete("/{tv_show_id}", status_code=204)
async def delete_tv_show(
    tv_show_id: str,
    current_user: dict = Depends(require_not_guest),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await tv_show_service.delete_tv_show(db, tv_show_id, current_user["username"])


@router.patch(
    "/{tv_show_id}/seasons/{season_number}",
    response_model=TvShow,
    dependencies=[Depends(require_not_guest)],
)
async def set_season_owned(
    tv_show_id: str,
    season_number: int,
    payload: SeasonOwnedUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await tv_show_service.set_season_owned(db, tv_show_id, season_number, payload.owned)


@router.patch(
    "/{tv_show_id}/seasons/{season_number}/episodes/{episode_number}",
    response_model=TvShow,
    dependencies=[Depends(require_not_guest)],
)
async def set_episode_watched(
    tv_show_id: str,
    season_number: int,
    episode_number: int,
    payload: EpisodeWatchedUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await tv_show_service.set_episode_watched(
        db, tv_show_id, season_number, episode_number, payload.watched, payload.watched_at
    )
