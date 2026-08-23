from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.backup import (
    DatabaseResetConfirm,
    DatabaseResetResult,
    SystemBackup,
    SystemRestoreResult,
)
from app.models.cert import (
    CertInstallConfirm,
    CertSignedComplete,
    CertStatus,
    CsrResult,
    Pkcs12Import,
)
from app.models.deploy import DeployRequest
from app.models.feature import FeatureListItem
from app.services import (
    audit_log_service,
    auth_service,
    cert_service,
    deploy_service,
    feature_list_service,
    system_backup_service,
)

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get(
    "/feature-list",
    response_model=list[FeatureListItem],
    dependencies=[Depends(get_current_user)],
)
async def feature_list() -> list[FeatureListItem]:
    """Feature #115 — oversigts-tabellen fra FEATURES.md (navn/status/version),
    nyeste først, så portalens brugere kan se hvad der bliver lavet uden adgang
    til det private GitHub-repo. Åben for enhver rolle, ikke kun admin."""
    return feature_list_service.get_feature_list()


@router.post("/deploy", status_code=202, dependencies=[Depends(require_admin)])
async def deploy(
    # Feature #194 — valgfrit request-body; en kalder der (som hidtil) ikke
    # sender noget body overhovedet får stadig standardværdien "main" i
    # stedet for en 422 for et "manglende" felt.
    payload: DeployRequest = DeployRequest(),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    deploy_service.trigger_deploy(payload.branch)
    await audit_log_service.record(
        db, current_user["username"], "deploy.triggered", f"branch: {payload.branch}"
    )
    return {"status": "started"}


@router.get("/deploy/status", dependencies=[Depends(require_admin)])
async def deploy_status() -> dict:
    """BUGS.md #36 — lader frontend skelne "intet nyt at hente" fra en reel
    deploy-fejl, i stedet for udelukkende at polle /api/health for et
    ændret build-nummer (som aldrig ændrer sig når der ikke var noget nyt)."""
    return deploy_service.get_deploy_status()


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


@router.post(
    "/reset", response_model=DatabaseResetResult, dependencies=[Depends(require_admin)]
)
async def reset(
    payload: DatabaseResetConfirm,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Wipes the film/TV library (feature #67) — movies, TV shows, their
    soft-deleted logs, tags, serial-number counters, Voldby BIO screenings/
    requests, and their seat reservations (BUGS.md #65 — reservations
    reference a screening_id, so they'd otherwise dangle once screenings
    are cleared). Confirmed by the admin's own password (stronger than the
    text confirmation phrase used by backup/restore, since this is more
    irreversible than a restore — there's no backup file to undo it with
    unless the admin took one first)."""
    await auth_service.verify_current_password(
        db, str(current_user["_id"]), payload.current_password
    )
    result = await system_backup_service.reset_library(db)
    await audit_log_service.record(
        db,
        current_user["username"],
        "database.reset",
        f"{result.movies_removed} film, {result.tv_shows_removed} TV-serier fjernet",
    )
    return result


@router.get("/cert", response_model=CertStatus, dependencies=[Depends(require_admin)])
async def get_cert_status():
    """Feature #73 — status of the currently-installed (or staged-but-not-
    yet-installed) production TLS certificate. Never exposes any key
    material, only public certificate fields."""
    return cert_service.get_status()


@router.post("/cert/csr", response_model=CsrResult, dependencies=[Depends(require_admin)])
async def create_csr(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Generates a fresh key + CSR for external signing (see DEPLOYMENT.md/
    BUGS.md #23) — non-destructive, doesn't touch production yet."""
    result = cert_service.generate_csr()
    await audit_log_service.record(db, current_user["username"], "tls_cert.csr_generated")
    return result


@router.post(
    "/cert/csr/complete", response_model=CertStatus, dependencies=[Depends(require_admin)]
)
async def complete_csr(
    payload: CertSignedComplete,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Pairs an externally-signed certificate with the pending CSR's key
    and stages it — still non-destructive, only `/cert/install` actually
    touches production."""
    result = cert_service.stage_signed_certificate(payload.certificate_pem)
    await audit_log_service.record(
        db, current_user["username"], "tls_cert.staged", f"CSR fuldført: {result.common_name}"
    )
    return result


@router.post("/cert/pkcs12", response_model=CertStatus, dependencies=[Depends(require_admin)])
async def import_pkcs12(
    payload: Pkcs12Import,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Alternative to the CSR flow — stages a ready-made PKCS12 (.pfx/.p12)
    bundle's cert+key pair. Still non-destructive until `/cert/install`."""
    result = cert_service.stage_pkcs12(payload.pkcs12_base64, payload.passphrase)
    await audit_log_service.record(
        db, current_user["username"], "tls_cert.staged", f"PKCS12 importeret: {result.common_name}"
    )
    return result


@router.post("/cert/install", status_code=202, dependencies=[Depends(require_admin)])
async def install_cert(
    payload: CertInstallConfirm,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """Triggers the actual production install (file swap + Caddy reload) of
    whatever is currently staged. Confirmed by the admin's own password —
    same reasoning as `/reset`: a broken install can take production HTTPS
    offline entirely, at least as irreversible as a database reset."""
    await auth_service.verify_current_password(
        db, str(current_user["_id"]), payload.current_password
    )
    cert_service.trigger_install()
    await audit_log_service.record(db, current_user["username"], "tls_cert.installed")
    return {"status": "started"}
