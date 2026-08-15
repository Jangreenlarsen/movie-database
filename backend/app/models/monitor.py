from pydantic import BaseModel

# Feature #154 — systemovervågning under Indstillinger → Drift.


class ServiceStatus(BaseModel):
    name: str
    # None = ukendt (fx uden for Linux/systemd, se NotSupportedOnThisPlatformError) —
    # ikke det samme som False (bekræftet stoppet).
    active: bool | None


class SystemHealth(BaseModel):
    platform: str
    cpu_percent: float | None
    memory_percent: float | None
    memory_used_mb: int | None
    memory_total_mb: int | None
    disk_percent: float | None
    disk_used_gb: float | None
    disk_total_gb: float | None
    uptime_seconds: int | None
    mongo_ok: bool
    services: list[ServiceStatus]


class RebootConfirm(BaseModel):
    """Samme mønster som DatabaseResetConfirm (feature #67) — en fuld
    server-genstart er mere forstyrrende end en almindelig admin-handling
    (hele appen, ikke kun web-laget, er nede i genstarts-perioden), så den
    kræver admins eget password som bekræftelse."""

    current_password: str
