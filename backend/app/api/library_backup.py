from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.backup import LibraryExport, LibraryImportResult
from app.services import audit_log_service, library_backup_service

# Feature #60 — high-level film/TV-library export/import, distinct from
# the full low-level system backup at /api/system/backup (feature #61).
router = APIRouter(prefix="/api/library", tags=["library-backup"])


@router.get("/export", response_model=LibraryExport, dependencies=[Depends(require_admin)])
async def export_library(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await library_backup_service.export_library(db)
    await audit_log_service.record(db, current_user["username"], "library_backup.exported")
    return result


@router.post(
    "/import", response_model=LibraryImportResult, dependencies=[Depends(require_admin)]
)
async def import_library(
    payload: LibraryExport,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Wholesale-replaces the `movies` and `tv_shows` collections with the
    given snapshot. Destructive — the frontend gates this behind an
    explicit confirmation phrase before ever calling it."""
    result = await library_backup_service.import_library(db, payload.movies, payload.tv_shows)
    await audit_log_service.record(
        db,
        current_user["username"],
        "library_backup.imported",
        f"{result.movies_imported} film, {result.tv_shows_imported} TV-serier",
    )
    return result
