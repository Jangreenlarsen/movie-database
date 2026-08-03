from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.backup import SystemBackup, SystemRestoreResult
from app.services import audit_log_service, deploy_service, system_backup_service

router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/deploy", status_code=202, dependencies=[Depends(require_admin)])
async def deploy(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    deploy_service.trigger_deploy()
    await audit_log_service.record(db, current_user["username"], "deploy.triggered")
    return {"status": "started"}


@router.get(
    "/backup", response_model=SystemBackup, dependencies=[Depends(require_admin)]
)
async def backup(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Full system backup (feature #61) — every collection except
    `system_settings` (see CLAUDE.md regel 6 / FEATURES.md #61)."""
    result = await system_backup_service.create_backup(db)
    await audit_log_service.record(db, current_user["username"], "system_backup.created")
    return result


@router.post(
    "/restore", response_model=SystemRestoreResult, dependencies=[Depends(require_admin)]
)
async def restore(
    payload: SystemBackup,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Wholesale-replaces every collection covered by `SystemBackup` with
    the given snapshot. Destructive — the frontend gates this behind an
    explicit confirmation phrase before ever calling it."""
    result = await system_backup_service.restore_backup(db, payload)
    await audit_log_service.record(
        db,
        current_user["username"],
        "system_backup.restored",
        f"{result.movies_imported} film, {result.tv_shows_imported} TV-serier, "
        f"{result.users_imported} brugere",
    )
    return result
