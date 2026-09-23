from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import require_not_guest
from app.db import get_database
from app.models.announcement import AnnouncementSendResult, PendingAnnouncement
from app.services import announcement_service, audit_log_service

# Feature #228 — køen til den samlede opdatering. Fælles for husstanden:
# enhver admin/standardbruger må se, rydde og sende den; gæster hverken
# tilføjer til biblioteket eller rører køen.
router = APIRouter(prefix="/api/announcements", tags=["announcements"])


@router.get("", response_model=list[PendingAnnouncement])
async def list_pending(
    current_user: dict = Depends(require_not_guest),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await announcement_service.list_pending(db)


# Registreret før /{announcement_id} — samme konvention som /reservations/mine.
@router.post("/send", response_model=AnnouncementSendResult)
async def send_digest(
    current_user: dict = Depends(require_not_guest),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await announcement_service.send(db, current_user)
    await audit_log_service.record(
        db,
        current_user["username"],
        "announcement.sent",
        f"Samlet opdatering med {result.sent_count} titel(ler)",
    )
    return result


@router.delete("/{announcement_id}", status_code=204)
async def remove(
    announcement_id: str,
    current_user: dict = Depends(require_not_guest),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await announcement_service.remove(db, announcement_id)
