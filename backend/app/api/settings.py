from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.settings import (
    ApiKeyTestResult,
    DigitalRenumberResult,
    PasswordPolicy,
    PasswordPolicyUpdate,
    PlexAutoImportPolicy,
    PlexAutoImportPolicyUpdate,
    ScreeningRequestPolicy,
    ScreeningRequestPolicyUpdate,
    SerialNumberConfig,
    SerialNumberConfigUpdate,
    SystemSettingsStatus,
    SystemSettingsUpdate,
    TestableApiKey,
    TestEmailRequest,
    TestModePolicy,
    TestModePolicyUpdate,
)
from app.services import audit_log_service, movie_service, system_settings_service

router = APIRouter(
    prefix="/api/settings", tags=["settings"], dependencies=[Depends(get_current_user)]
)


@router.get("/serial-number", response_model=SerialNumberConfig)
async def get_serial_number_config(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await movie_service.get_serial_number_config(db)


@router.patch("/serial-number", response_model=SerialNumberConfig, dependencies=[Depends(require_admin)])
async def update_serial_number_config(
    payload: SerialNumberConfigUpdate, db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await movie_service.update_serial_number_config(db, payload)


@router.post(
    "/serial-number/renumber-digital",
    response_model=DigitalRenumberResult,
    dependencies=[Depends(require_admin)],
)
async def renumber_digital_serial_number(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Feature #188 (Jan, 2026-08-21: "Nulstil til at starte fra 1", efter
    BUGS.md #81 blev forklaret) — engangs-omnummerering af D#-serien.
    Rører aldrig fysiske (M#/T#) poster, se
    `digital_serial_repository.renumber_from_one`s docstring."""
    renumbered = await movie_service.renumber_digital_serial_from_one(db)
    await audit_log_service.record(
        db,
        current_user["username"],
        "digital_serial.renumbered",
        f"{renumbered} digitale poster omnummereret til at starte fra D#1",
    )
    return DigitalRenumberResult(renumbered=renumbered)


@router.get(
    "/system", response_model=SystemSettingsStatus, dependencies=[Depends(require_admin)]
)
async def get_system_settings(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await system_settings_service.get_status(db)


@router.patch(
    "/system", response_model=SystemSettingsStatus, dependencies=[Depends(require_admin)]
)
async def update_system_settings(
    payload: SystemSettingsUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await system_settings_service.update_settings(db, payload)
    # Log which keys changed, never the values themselves (CLAUDE.md regel 6).
    changed_keys = sorted(payload.model_dump(exclude_unset=True).keys())
    if changed_keys:
        await audit_log_service.record(
            db, current_user["username"], "system_settings.updated", ", ".join(changed_keys)
        )
    return result


@router.post(
    "/system/test/{key}",
    response_model=ApiKeyTestResult,
    dependencies=[Depends(require_admin)],
)
async def test_system_setting(key: TestableApiKey):
    """Feature #75 — `key` er begrænset til `TestableApiKey`s Literal, så
    FastAPI selv afviser (422) ethvert andet felt-navn end de fem der
    faktisk har et testkald bag sig."""
    return await system_settings_service.test_connection(key)


@router.post(
    "/system/test-email",
    response_model=ApiKeyTestResult,
    dependencies=[Depends(require_admin)],
)
async def send_test_email(payload: TestEmailRequest):
    """Feature #199 — ægte ende-til-ende-afsendelse til en valgfri adresse
    (ikke nødvendigvis kalderens egen), adskilt fra test_system_setting
    ovenfor. Delt `ApiKeyTestResult`-svarform, samme UX-mønster som "Test
    forbindelse"."""
    return await system_settings_service.send_test_email(payload.to)


@router.get(
    "/password-policy", response_model=PasswordPolicy, dependencies=[Depends(require_admin)]
)
async def get_password_policy(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await system_settings_service.get_password_policy(db)


@router.patch(
    "/password-policy", response_model=PasswordPolicy, dependencies=[Depends(require_admin)]
)
async def update_password_policy(
    payload: PasswordPolicyUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await system_settings_service.update_password_policy(db, payload)
    # I modsætning til /system ovenfor er politik-værdierne ikke hemmelige
    # (CLAUDE.md regel 6 gælder ikke her) — audit-loggen kan derfor trygt
    # vise de faktiske nye værdier, ikke kun feltnavnene.
    changes = payload.model_dump(exclude_unset=True)
    if changes:
        detail = ", ".join(f"{key}={value}" for key, value in changes.items())
        await audit_log_service.record(
            db, current_user["username"], "password_policy.updated", detail
        )
    return result


@router.get("/screening-request-policy", response_model=ScreeningRequestPolicy)
async def get_screening_request_policy(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Feature #177/#186 — bevidst IKKE admin-only (i modsætning til de
    øvrige politik-endpoints ovenfor): enhver bruger skal selv kunne se om
    tidspunkt-feltet reelt er påkrævet, for at UI'et (Ønsk visning-knappen)
    kan afspejle det rigtigt uden at gætte. Router-niveauets
    `Depends(get_current_user)` er stadig nok — ikke en hemmelighed."""
    return await system_settings_service.get_screening_request_policy(db)


@router.patch(
    "/screening-request-policy",
    response_model=ScreeningRequestPolicy,
    dependencies=[Depends(require_admin)],
)
async def update_screening_request_policy(
    payload: ScreeningRequestPolicyUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await system_settings_service.update_screening_request_policy(db, payload)
    changes = payload.model_dump(exclude_unset=True)
    if changes:
        detail = ", ".join(f"{key}={value}" for key, value in changes.items())
        await audit_log_service.record(
            db, current_user["username"], "screening_request_policy.updated", detail
        )
    return result


@router.get(
    "/plex-auto-import", response_model=PlexAutoImportPolicy, dependencies=[Depends(require_admin)]
)
async def get_plex_auto_import_policy(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Feature #181 (Jan: "vi skal have en automatisk scan af plex media
    server for ny film og tv serie, i dag er det en manual funktion")."""
    return await system_settings_service.get_plex_auto_import_policy(db)


@router.patch(
    "/plex-auto-import",
    response_model=PlexAutoImportPolicy,
    dependencies=[Depends(require_admin)],
)
async def update_plex_auto_import_policy(
    payload: PlexAutoImportPolicyUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await system_settings_service.update_plex_auto_import_policy(db, payload)
    changes = payload.model_dump(exclude_unset=True)
    if changes:
        detail = ", ".join(f"{key}={value}" for key, value in changes.items())
        await audit_log_service.record(
            db, current_user["username"], "plex_auto_import_policy.updated", detail
        )
    return result


@router.get("/test-mode", response_model=TestModePolicy, dependencies=[Depends(require_admin)])
async def get_test_mode_policy(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Feature #217 (Jan: "vi skal have en funktion for adm i settings hvor
    vi kan sætte at 'test' tilstand som primæret vil betyde at email og
    beskeder ikke sendes ud af system i test mode"). Admin-only — det er en
    operationel afbryder, ingen almindelig bruger har brug for at kende
    tilstanden af (i modsætning til fx screening-request-policy)."""
    return await system_settings_service.get_test_mode_policy(db)


@router.patch("/test-mode", response_model=TestModePolicy, dependencies=[Depends(require_admin)])
async def update_test_mode_policy(
    payload: TestModePolicyUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await system_settings_service.update_test_mode_policy(db, payload)
    changes = payload.model_dump(exclude_unset=True)
    if changes:
        detail = ", ".join(f"{key}={value}" for key, value in changes.items())
        await audit_log_service.record(db, current_user["username"], "test_mode_policy.updated", detail)
    return result
