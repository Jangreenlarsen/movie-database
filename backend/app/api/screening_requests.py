from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin, require_not_guest
from app.db import get_database
from app.models.screening import ScreeningRequest, ScreeningRequestCreate, ScreeningRequestUpdate
from app.services import audit_log_service, screening_service

# Feature #62 — any logged-in user can request a title be screened; only
# an admin can list/review/decline requests (see /api/screenings for
# turning a request into an actual dated screening, feature #63).
router = APIRouter(
    prefix="/api/screening-requests",
    tags=["screening-requests"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=ScreeningRequest, status_code=201)
async def create_request(
    payload: ScreeningRequestCreate,
    current_user: dict = Depends(require_not_guest),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await screening_service.request_screening(
        db, payload.media_kind, payload.movie_id, payload.tv_show_id, current_user["username"]
    )


@router.get("", response_model=list[ScreeningRequest], dependencies=[Depends(require_admin)])
async def list_requests(
    status: str | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await screening_service.list_requests(db, status)


# Registered before /{request_id} — same convention as movies.py/tv_shows.py.
@router.get("/mine", response_model=list[ScreeningRequest])
async def list_my_requests(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await screening_service.list_my_requests(db, current_user["username"])


@router.patch(
    "/{request_id}", response_model=ScreeningRequest, dependencies=[Depends(require_admin)]
)
async def update_request(
    request_id: str,
    payload: ScreeningRequestUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    # Only "declined" is accepted by ScreeningRequestUpdate — becoming
    # "scheduled" only happens as a side effect of POST /api/screenings.
    updated = await screening_service.decline_request(db, request_id)
    await audit_log_service.record(
        db, current_user["username"], "screening_request.declined", updated.title
    )
    return updated
