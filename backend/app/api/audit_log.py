from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import require_admin
from app.db import get_database
from app.models.audit_log import AuditLogPage
from app.services import audit_log_service

# Feature #65 — admin-only trail of security-/data-relevant actions
# (role changes, system-key updates, deploy, backup/restore, cinema
# scheduling/declining). Write side has no endpoint on purpose: entries
# are only ever recorded as a side effect of the actions themselves.
router = APIRouter(prefix="/api/audit-log", tags=["audit-log"])


@router.get("", response_model=AuditLogPage, dependencies=[Depends(require_admin)])
async def list_audit_log(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await audit_log_service.list_entries(db, skip, limit)
