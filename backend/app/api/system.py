from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import require_admin
from app.db import get_database
from app.models.backup import SystemBackup, SystemRestoreResult
from app.services import deploy_service, system_backup_service

router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/deploy", status_code=202, dependencies=[Depends(require_admin)])
async def deploy() -> dict:
    deploy_service.trigger_deploy()
    return {"status": "started"}


@router.get(
    "/backup", response_model=SystemBackup, dependencies=[Depends(require_admin)]
)
async def backup(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Full system backup (feature #61) — every collection except
    `system_settings` (see CLAUDE.md regel 6 / FEATURES.md #61)."""
    return await system_backup_service.create_backup(db)


@router.post(
    "/restore", response_model=SystemRestoreResult, dependencies=[Depends(require_admin)]
)
async def restore(
    payload: SystemBackup, db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Wholesale-replaces every collection covered by `SystemBackup` with
    the given snapshot. Destructive — the frontend gates this behind an
    explicit confirmation phrase before ever calling it."""
    return await system_backup_service.restore_backup(db, payload)
