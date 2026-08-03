from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import require_admin
from app.db import get_database
from app.models.backup import LibraryExport, LibraryImportResult
from app.services import library_backup_service

# Feature #60 — high-level film/TV-library export/import, distinct from
# the full low-level system backup at /api/system/backup (feature #61).
router = APIRouter(prefix="/api/library", tags=["library-backup"])


@router.get("/export", response_model=LibraryExport, dependencies=[Depends(require_admin)])
async def export_library(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await library_backup_service.export_library(db)


@router.post(
    "/import", response_model=LibraryImportResult, dependencies=[Depends(require_admin)]
)
async def import_library(
    payload: LibraryExport, db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Wholesale-replaces the `movies` and `tv_shows` collections with the
    given snapshot. Destructive — the frontend gates this behind an
    explicit confirmation phrase before ever calling it."""
    return await library_backup_service.import_library(db, payload.movies, payload.tv_shows)
