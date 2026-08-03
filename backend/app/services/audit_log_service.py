import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.audit_log import AuditLogEntry, AuditLogPage
from app.repositories import audit_log_repository

logger = logging.getLogger("moviedb")


def _to_model(document: dict) -> AuditLogEntry:
    return AuditLogEntry(
        id=str(document["_id"]),
        actor=document["actor"],
        action=document["action"],
        detail=document.get("detail"),
        created_at=document["created_at"],
    )


async def record(
    db: AsyncIOMotorDatabase, actor: str, action: str, detail: str | None = None
) -> None:
    """Best-effort audit trail (feature #65) — same philosophy as the
    Plex/OMDb integrations: never blocks or fails the admin action it's
    logging. A DB hiccup here shouldn't turn e.g. a role change into a
    500; it's logged instead so the gap is at least visible in the
    server log (CLAUDE.md regel 11)."""
    try:
        await audit_log_repository.insert(db, actor, action, detail)
    except Exception:
        logger.exception("Kunne ikke skrive audit-log entry (action=%s)", action)


async def list_entries(db: AsyncIOMotorDatabase, skip: int, limit: int) -> AuditLogPage:
    documents = await audit_log_repository.list_paginated(db, skip, limit)
    total = await audit_log_repository.count(db)
    return AuditLogPage(entries=[_to_model(doc) for doc in documents], total=total)
