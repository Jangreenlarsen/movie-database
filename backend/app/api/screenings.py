from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.screening import Screening, ScreeningCreate, ScreeningUpdate
from app.services import audit_log_service, screening_service

# Feature #63 — admin-scheduled screenings, backing the Voldby BIO calendar.
# GET has no auth dependency at all (feature #70) — the public /bio page
# must work for anonymous visitors, not just logged-in users. Every
# mutating route below still requires admin explicitly via require_admin
# (which itself depends on get_current_user), so nothing here weakens
# write access — only the read-only "what's on" listing became public.
router = APIRouter(prefix="/api/screenings", tags=["screenings"])


@router.get("", response_model=list[Screening])
async def list_screenings(
    upcoming: bool = Query(default=False, description="True limits to screenings not yet in the past"),
    past: bool = Query(default=False, description="True limits to past screenings, newest first (feature #130 history)"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await screening_service.list_screenings(db, upcoming, past)


@router.post("", response_model=Screening, status_code=201, dependencies=[Depends(require_admin)])
async def create_screening(
    payload: ScreeningCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await screening_service.create_screening(db, payload, current_user)
    await audit_log_service.record(
        db,
        current_user["username"],
        "screening.scheduled",
        f"{result.title} d. {result.scheduled_at:%d-%m-%Y %H:%M}",
    )
    return result


@router.patch("/{screening_id}", response_model=Screening, dependencies=[Depends(require_admin)])
async def update_screening(
    screening_id: str,
    payload: ScreeningUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await screening_service.update_screening(db, screening_id, payload)


@router.delete("/{screening_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_screening(
    screening_id: str, db: AsyncIOMotorDatabase = Depends(get_database)
):
    await screening_service.delete_screening(db, screening_id)
