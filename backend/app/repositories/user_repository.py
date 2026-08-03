from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "users"

DEFAULT_SETTINGS = {
    "sort_field": None,
    "sort_direction": None,
    "visible_fields": {
        "year": True,
        "tags": True,
        "format": False,
        "audio_types": False,
        "media_type": False,
        "rating": False,
        "runtime": False,
    },
    "sort_levels": [],
    "sort_presets": [],
    "tv_visible_fields": {
        "year": True,
        "tags": True,
        "format": False,
        "audio_types": False,
        "media_type": False,
        "rating": False,
        "runtime": False,
    },
    "tv_sort_levels": [],
    "tv_sort_presets": [],
    "card_size": "medium",
}


async def _migrate_username_normalized(db: AsyncIOMotorDatabase) -> None:
    """Backfills `username_normalized` (lowercased, used for case-insensitive
    login/uniqueness — see BUGS.md #21: iOS Safari auto-capitalizes the
    first letter of a text input by default unless it opts out, which
    silently broke login for any username with mixed/lower case) for any
    user document created before this field existed."""
    cursor = db[COLLECTION].find({"username_normalized": {"$exists": False}})
    async for doc in cursor:
        await db[COLLECTION].update_one(
            {"_id": doc["_id"]}, {"$set": {"username_normalized": doc["username"].lower()}}
        )


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await _migrate_username_normalized(db)

    # Uniqueness now lives on the normalized field (case-insensitive), not
    # the raw one — Mongo won't redefine an existing same-named index under
    # different options, so the old one is dropped first if present (same
    # migration pattern as movie_repository's serial_number sparse-index
    # switch).
    existing_indexes = await db[COLLECTION].index_information()
    if "username_1" in existing_indexes:
        await db[COLLECTION].drop_index("username_1")
    await db[COLLECTION].create_index("username_normalized", unique=True)


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_username_normalized(db: AsyncIOMotorDatabase, normalized_username: str) -> dict | None:
    return await db[COLLECTION].find_one({"username_normalized": normalized_username})


async def find_by_id(db: AsyncIOMotorDatabase, user_id: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})


async def update_settings(db: AsyncIOMotorDatabase, user_id: str, settings: dict) -> dict | None:
    """Updates only the given top-level `settings.*` keys via dotted-path
    `$set`s — atomic per-field, so concurrent requests touching different
    keys (e.g. `sort_levels` vs `sort_presets`) can never race and lose one
    another's write, unlike a read-whole-settings-then-overwrite approach."""
    if not ObjectId.is_valid(user_id):
        return None
    dotted_updates = {f"settings.{key}": value for key, value in settings.items()}
    if dotted_updates:
        await db[COLLECTION].update_one({"_id": ObjectId(user_id)}, {"$set": dotted_updates})
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})


async def count(db: AsyncIOMotorDatabase) -> int:
    return await db[COLLECTION].count_documents({})


async def count_by_role(db: AsyncIOMotorDatabase, role: str) -> int:
    return await db[COLLECTION].count_documents({"role": role})


async def list_all(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db[COLLECTION].find().sort("created_at", 1)
    return await cursor.to_list(length=1000)


async def set_role(db: AsyncIOMotorDatabase, user_id: str, role: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(user_id)}, {"$set": {"role": role}})
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})


async def set_password_hash(db: AsyncIOMotorDatabase, user_id: str, password_hash: str) -> None:
    await db[COLLECTION].update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"password_hash": password_hash}}
    )
