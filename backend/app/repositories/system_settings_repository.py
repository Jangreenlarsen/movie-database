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
    "upc_api_key",
    "discogs_token",
    "upcdatabase_token",
    "omdb_api_key",
    "plex_server_url",
    "plex_token",
)


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
