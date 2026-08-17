from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "system_settings"
DOC_ID = "system"

# Keys that may be overridden via the admin UI. Kept in sync with
# `models.settings.SystemSettingsUpdate`. Storage/persistence is identical
# for all of them regardless of whether the service layer treats a given
# key as a masked secret or a plainly-visible value (feature #45's
# plex_server_url) — that distinction only matters when deciding what to
# expose in a GET response, not how the override itself is stored.
OVERRIDABLE_KEYS = (
    "tmdb_api_token",
    "discogs_token",
    "upcdatabase_token",
    "ean_search_api_key",
    "omdb_api_key",
    "plex_server_url",
    "plex_token",
    "primary_barcode_source",
)

# The only two overridable keys that aren't secrets (CLAUDE.md regel 6 —
# already returned with their real value by GET /api/settings/system, unlike
# the other six which are masked). Centralised here rather than duplicated
# in system_settings_service/system_backup_service, since both need the same
# classification of the same keys.
PLAIN_KEYS = ("plex_server_url", "primary_barcode_source")


async def get_overrides(db: AsyncIOMotorDatabase) -> dict:
    """Returns only the keys that currently have a custom (DB-stored)
    override. A missing key means "no override — use .env"."""
    doc = await db[COLLECTION].find_one({"_id": DOC_ID})
    if doc is None:
        return {}
    return {key: doc[key] for key in OVERRIDABLE_KEYS if key in doc}


async def apply_updates(db: AsyncIOMotorDatabase, updates: dict) -> dict:
    """`updates` maps key -> new string value ("" means clear the override).
    Persists via `$set`/`$unset` (never a read-modify-write of the whole
    doc), then returns the fresh set of overrides."""
    to_set = {key: value for key, value in updates.items() if value != ""}
    to_unset = {key: "" for key, value in updates.items() if value == ""}

    mongo_update: dict = {}
    if to_set:
        mongo_update["$set"] = to_set
    if to_unset:
        mongo_update["$unset"] = to_unset

    if mongo_update:
        await db[COLLECTION].update_one({"_id": DOC_ID}, mongo_update, upsert=True)

    return await get_overrides(db)


# Feature #174 — samme dokument som OVERRIDABLE_KEYS ovenfor, men egne
# typede (int/bool) felter uden noget "" = ryd-til-.env-koncept (der er
# intet .env at falde tilbage til for en adgangskode-politik), så de holdes
# adskilt fra apply_updates' rent streng-baserede $set/$unset-mønster.
PASSWORD_POLICY_KEYS = (
    "password_min_length",
    "password_require_uppercase",
    "password_require_lowercase",
    "password_require_digit",
)


async def get_password_policy_overrides(db: AsyncIOMotorDatabase) -> dict:
    """Returns only the policy keys that currently have a custom (DB-stored)
    value. A missing key means "use the code default from Settings"."""
    doc = await db[COLLECTION].find_one({"_id": DOC_ID})
    if doc is None:
        return {}
    return {key: doc[key] for key in PASSWORD_POLICY_KEYS if key in doc}


async def apply_password_policy_update(db: AsyncIOMotorDatabase, updates: dict) -> dict:
    """`updates` maps key -> new typed value. Always a `$set` (no "clear"
    concept, unlike apply_updates above)."""
    if updates:
        await db[COLLECTION].update_one({"_id": DOC_ID}, {"$set": updates}, upsert=True)
    return await get_password_policy_overrides(db)
