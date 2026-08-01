from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import ENV_DEFAULT_API_KEYS, settings
from app.models.settings import ApiKeyStatus, SystemSettingsStatus, SystemSettingsUpdate
from app.repositories import system_settings_repository

KEYS = system_settings_repository.OVERRIDABLE_KEYS


async def apply_overrides_on_startup(db: AsyncIOMotorDatabase) -> None:
    """Called once from the app lifespan, after the .env-derived `settings`
    singleton exists but before anything else reads from it — so admin-set
    overrides from a previous run take effect immediately without requiring
    the .env file itself to be edited."""
    overrides = await system_settings_repository.get_overrides(db)
    for key, value in overrides.items():
        setattr(settings, key, value)


async def get_status(db: AsyncIOMotorDatabase) -> SystemSettingsStatus:
    overrides = await system_settings_repository.get_overrides(db)
    statuses = {}
    for key in KEYS:
        value = getattr(settings, key)
        if key in overrides:
            source = "custom"
        elif value:
            source = "env"
        else:
            source = "unset"
        statuses[key] = ApiKeyStatus(configured=bool(value), source=source)
    return SystemSettingsStatus(**statuses)


async def update_settings(
    db: AsyncIOMotorDatabase, payload: SystemSettingsUpdate
) -> SystemSettingsStatus:
    updates = {
        key: value.strip()
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    await system_settings_repository.apply_updates(db, updates)

    for key, value in updates.items():
        setattr(settings, key, value if value != "" else ENV_DEFAULT_API_KEYS[key])

    return await get_status(db)
