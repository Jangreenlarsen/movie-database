from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.monitor import RebootConfirm, SystemHealth
from app.services import audit_log_service, auth_service, monitor_service

# Feature #154 — systemovervågning (CPU/RAM/disk/tjeneste-status) + genstart,
# under Indstillinger → Drift. Admin-only hele vejen (samme begrundelse som
# resten af "Drift"-fanen: driftsdata og genstarts-knapper er ikke noget en
# almindelig bruger skal kunne se eller trykke på).
router = APIRouter(prefix="/api/system/monitor", tags=["monitor"], dependencies=[Depends(require_admin)])


@router.get("", response_model=SystemHealth)
async def get_health(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await monitor_service.get_health(db)


@router.post("/restart-service", status_code=202)
async def restart_service(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """Genstarter kun moviedb-backend + genindlæser Caddy — samme lette
    handling "Opdatér fra GitHub" (feature #20) også udløser som sidste
    trin, blot uden selve git pull/npm build. Ingen adgangskode-bekræftelse
    nødvendig (samme lave friktion som deploy-knappen)."""
    monitor_service.restart_service()
    await audit_log_service.record(db, current_user["username"], "system.service_restarted")
    return {"status": "triggered"}


@router.post("/reboot", status_code=202)
async def reboot(
    payload: RebootConfirm,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """Genstarter hele serveren. Kræver admins eget password — samme
    begrundelse som database-reset (feature #67): mere forstyrrende end en
    almindelig admin-handling, hele appen (ikke kun web-laget) er nede i
    genstarts-perioden."""
    await auth_service.verify_current_password(
        db, str(current_user["_id"]), payload.current_password
    )
    monitor_service.trigger_reboot()
    await audit_log_service.record(db, current_user["username"], "system.reboot_triggered")
    return {"status": "triggered"}
