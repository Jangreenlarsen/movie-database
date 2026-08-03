from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.settings import (
    SerialNumberConfig,
    SerialNumberConfigUpdate,
    SystemSettingsStatus,
    SystemSettingsUpdate,
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
