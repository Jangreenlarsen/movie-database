from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

COLLECTION = "tv_shows"
DELETED_COLLECTION = "deleted_tv_shows"
COUNTERS_COLLECTION = "counters"
# Separate counter from movies' "movie_serial" — TV shows are a fully
# separate resource (Jan's explicit choice, 2026-08-02), so a separate
# physical numbering sequence is the more conservative default. Easy to
# unify later if that turns out to be wrong.
SERIAL_COUNTER_ID = "tv_show_serial"
DEFAULT_SERIAL_CONFIG = {"next_value": 1, "increment": 1, "padding_width": 0}
MAX_SERIAL_ASSIGN_ATTEMPTS = 10_000

SORT_FIELDS = {
    "name": "name",
    "year": "year",
    "serial_number": "serial_number",
    "created_at": "created_at",
    "rating": "rating",
    "personal_rating": "personal_rating",
    "format": "format",
    "audio_types": "audio_types",
    "media_type": "media_type",
    "location": "location",
    "owner": "owner",
    "registered_by": "registered_by",
    "watched_at": "watched_at",
}
DEFAULT_SORT_FIELD = "created_at"
MAX_SORT_LEVELS = 3


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    collection = db[COLLECTION]
    await collection.create_index([("name", "text"), ("overview", "text")])
    await collection.create_index("tags_normalized")
    await collection.create_index("barcode", unique=True, sparse=True)
    await collection.create_index("format")
    await collection.create_index("audio_types")
    await collection.create_index("media_type")
    await collection.create_index("serial_number", unique=True, sparse=True)
    await collection.create_index("is_wishlist")
    await collection.create_index("rating")
    await collection.create_index("personal_rating")
    await collection.create_index("watched")
    await collection.create_index("watched_at")
    await collection.create_index("year")
    await collection.create_index("created_at")
    await collection.create_index("location")
    await collection.create_index("owner")
    await collection.create_index("registered_by")
    await db[DELETED_COLLECTION].create_index("deleted_at")


async def _ensure_serial_config(db: AsyncIOMotorDatabase) -> dict:
    doc = await db[COUNTERS_COLLECTION].find_one({"_id": SERIAL_COUNTER_ID})
    if doc is None:
        doc = {"_id": SERIAL_COUNTER_ID, **DEFAULT_SERIAL_CONFIG}
        await db[COUNTERS_COLLECTION].insert_one(doc)
    return doc


async def next_serial_number(db: AsyncIOMotorDatabase) -> int:
    """Same race-safe skip-collisions approach as movie_repository's
    version — see there for the full rationale."""
    for _ in range(MAX_SERIAL_ASSIGN_ATTEMPTS):
        config = await _ensure_serial_config(db)
        increment = config.get("increment", DEFAULT_SERIAL_CONFIG["increment"])

        before = await db[COUNTERS_COLLECTION].find_one_and_update(
            {"_id": SERIAL_COUNTER_ID},
            {"$inc": {"next_value": increment}},
            return_document=ReturnDocument.BEFORE,
        )
        candidate = before["next_value"]

        if await db[COLLECTION].find_one({"serial_number": candidate}, {"_id": 1}) is None:
            return candidate

    raise RuntimeError("Could not find a free serial number after many attempts")


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_id(db: AsyncIOMotorDatabase, tv_show_id: str) -> dict | None:
    if not ObjectId.is_valid(tv_show_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(tv_show_id)})


async def find_by_serial_number(db: AsyncIOMotorDatabase, serial_number: int) -> dict | None:
    return await db[COLLECTION].find_one({"serial_number": serial_number})


async def find_by_tmdb_id(db: AsyncIOMotorDatabase, tmdb_id: int) -> list[dict]:
    cursor = db[COLLECTION].find({"tmdb_id": tmdb_id})
    return await cursor.to_list(length=100)


async def find_all_with_tmdb_id(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db[COLLECTION].find({"tmdb_id": {"$ne": None}})
    return await cursor.to_list(length=10_000)


async def set_serial_number(db: AsyncIOMotorDatabase, tv_show_id: str, serial_number: int) -> None:
    await db[COLLECTION].update_one(
        {"_id": ObjectId(tv_show_id)}, {"$set": {"serial_number": serial_number}}
    )


async def clear_serial_number(db: AsyncIOMotorDatabase, tv_show_id: str) -> None:
    await db[COLLECTION].update_one(
        {"_id": ObjectId(tv_show_id)}, {"$unset": {"serial_number": ""}}
    )


async def find_many(
    db: AsyncIOMotorDatabase,
    query: str | None,
    normalized_tags: list[str] | None,
    formats: list[str] | None = None,
    audio_types: list[str] | None = None,
    media_types: list[str] | None = None,
    sort_spec: list[tuple[str, int]] | None = None,
    is_wishlist: bool = False,
    watched: bool | None = None,
) -> list[dict]:
    filter_: dict = {"is_wishlist": True if is_wishlist else {"$ne": True}}
    if query:
        filter_["$text"] = {"$search": query}
    if normalized_tags:
        filter_["tags_normalized"] = {"$all": normalized_tags}
    if formats:
        filter_["format"] = {"$in": formats}
    if audio_types:
        filter_["audio_types"] = {"$in": audio_types}
    if media_types:
        filter_["media_type"] = {"$in": media_types}
    if watched is not None:
        filter_["watched"] = True if watched else {"$ne": True}

    cursor = db[COLLECTION].find(filter_)
    cursor = cursor.sort(sort_spec) if sort_spec else cursor.sort(DEFAULT_SORT_FIELD, -1)
    return await cursor.to_list(length=500)


async def update(db: AsyncIOMotorDatabase, tv_show_id: str, fields: dict) -> dict | None:
    if not ObjectId.is_valid(tv_show_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(tv_show_id)}, {"$set": fields})
    return await db[COLLECTION].find_one({"_id": ObjectId(tv_show_id)})


async def delete(db: AsyncIOMotorDatabase, tv_show_id: str) -> bool:
    if not ObjectId.is_valid(tv_show_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(tv_show_id)})
    return result.deleted_count > 0


async def archive_deleted(db: AsyncIOMotorDatabase, tv_show_doc: dict, deleted_by: str) -> None:
    await db[DELETED_COLLECTION].insert_one(
        {
            "tv_show_id": tv_show_doc["_id"],
            "serial_number": tv_show_doc.get("serial_number"),
            "name": tv_show_doc["name"],
            "year": tv_show_doc.get("year"),
            "format": tv_show_doc.get("format"),
            "deleted_at": datetime.now(timezone.utc),
            "deleted_by": deleted_by,
        }
    )


async def list_deleted(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db[DELETED_COLLECTION].find().sort("deleted_at", -1)
    return await cursor.to_list(length=1000)


async def set_season_owned(db: AsyncIOMotorDatabase, tv_show_id: str, season_number: int, owned: bool) -> bool:
    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(tv_show_id), "seasons.season_number": season_number},
        {"$set": {"seasons.$.owned": owned}},
    )
    return result.matched_count > 0


async def set_season_episodes(
    db: AsyncIOMotorDatabase, tv_show_id: str, season_number: int, episodes: list[dict]
) -> bool:
    """Atomically replaces one season's *entire* episode list via the
    positional `$` update operator. Used both to populate a season right
    after its lazy TMDb fetch, and to persist a single episode's toggled
    `watched` flag (the caller — tv_show_service — reads the current list,
    mutates one entry in Python, and passes the whole list back here).
    Bounds any read-modify-write race to "two concurrent episode toggles
    within the same season", never across seasons or the rest of the
    document — deliberately avoids MongoDB `arrayFilters`, whose mongomock
    support is inconsistent (see movie_repository's label-migration note)."""
    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(tv_show_id), "seasons.season_number": season_number},
        {"$set": {"seasons.$.episodes": episodes}},
    )
    return result.matched_count > 0
