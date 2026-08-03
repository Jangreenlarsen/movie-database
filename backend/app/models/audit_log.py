from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    id: str
    actor: str
    action: str
    detail: str | None = None
    created_at: datetime


class AuditLogPage(BaseModel):
    entries: list[AuditLogEntry] = Field(default_factory=list)
    total: int
