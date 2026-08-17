from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.settings import (
    ApiKeyTestResult,
    PasswordPolicy,
    PasswordPolicyUpdate,
    SerialNumberConfig,
    SerialNumberConfigUpdate,
    SystemSettingsStatus,
    SystemSettingsUpdate,
    TestableApiKey,
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
