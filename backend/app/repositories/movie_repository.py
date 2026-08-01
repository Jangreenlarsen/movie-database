from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

COLLECTION = "movies"
DELETED_COLLECTION = "deleted_movies"
COUNTERS_COLLECTION = "counters"
SERIAL_COUNTER_ID = "movie_serial"
DEFAULT_SERIAL_CONFIG = {"next_value": 1, "increment": 1, "padding_width": 0}
MAX_SERIAL_ASSIGN_ATTEMPTS = 10_000

# Whitelist mapping API-facing sort keys -> actual document fields, so an
# arbitrary/unindexed field can never be requested via the query string.
SORT_FIELDS = {
    "title": "title",
    "year": "year",
    "serial_number": "serial_number",
    "rating": "rating",
}
DEFAULT_SORT_FIELD = "created_at"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    collection = db[COLLECTION]
    await collection.create_index([("title", "text"), ("overview", "text")])
    await collection.create_index("tags_normalized")
    await collection.create_index("barcode", unique=True, sparse=True)
    await collection.create_index("format")
    await collection.create_index("audio_types")
    await collection.create_index("serial_number", unique=True)
    await collection.create_index("rating")
    await collection.create_index("year")
    await db[DELETED_COLLECTION].create_index("deleted_at")


async def _ensure_serial_config(db: AsyncIOMotorDatabase) -> dict:
    doc = await db[COUNTERS_COLLECTION].find_one({"_id": SERIAL_COUNTER_ID})
    if doc is None:
        doc = {"_id": SERIAL_COUNTER_ID, **DEFAULT_SERIAL_CONFIG}
        await db[COUNTERS_COLLECTION].insert_one(doc)
        return doc

    if "next_value" not in doc:
        # Migrate the pre-v0.9.0 counter shape ({"value": <last assigned>})
        # to the configurable one ({"next_value": <to assign next>, ...}).
        next_value = doc.get("value", 0) + 1
        await db[COUNTERS_COLLECTION].update_one(
            {"_id": SERIAL_COUNTER_ID},
            {"$set": {"next_value": next_value}, "$unset": {"value": ""}},
        )
        doc = await db[COUNTERS_COLLECTION].find_one({"_id": SERIAL_COUNTER_ID})

    return doc


async def get_serial_config(db: AsyncIOMotorDatabase) -> dict:
    config = await _ensure_serial_config(db)
    return {
        "start_number": config.get("next_value", DEFAULT_SERIAL_CONFIG["next_value"]),
        "increment": config.get("increment", DEFAULT_SERIAL_CONFIG["increment"]),
        "padding_width": config.get("padding_width", DEFAULT_SERIAL_CONFIG["padding_width"]),
    }


async def update_serial_config(db: AsyncIOMotorDatabase, updates: dict) -> dict:
    """`start_number` is a one-off "assign this to the next movie" action, not
    a historical origin — it directly moves the next-value pointer.
    `increment` only changes the step size going forward. `padding_width`
    is display-only."""
    await _ensure_serial_config(db)

    mongo_updates: dict = {}
    if "start_number" in updates:
        mongo_updates["next_value"] = updates["start_number"]
    if "increment" in updates:
        mongo_updates["increment"] = updates["increment"]
    if "padding_width" in updates:
        mongo_updates["padding_width"] = updates["padding_width"]

    if mongo_updates:
        await db[COUNTERS_COLLECTION].update_one(
            {"_id": SERIAL_COUNTER_ID}, {"$set": mongo_updates}
        )
    return await get_serial_config(db)


async def next_serial_number(db: AsyncIOMotorDatabase) -> int:
    """Race-safe even under concurrent creates. If the next value is already
    taken (possible right after `start_number` was moved onto an
    already-assigned number), keeps advancing by `increment` until a free
    one is found."""
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


async def find_by_id(db: AsyncIOMotorDatabase, movie_id: str) -> dict | None:
    if not ObjectId.is_valid(movie_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(movie_id)})


async def find_by_serial_number(db: AsyncIOMotorDatabase, serial_number: int) -> dict | None:
    return await db[COLLECTION].find_one({"serial_number": serial_number})


async def set_serial_number(db: AsyncIOMotorDatabase, movie_id: str, serial_number: int) -> None:
    await db[COLLECTION].update_one(
        {"_id": ObjectId(movie_id)}, {"$set": {"serial_number": serial_number}}
    )


async def find_many(
    db: AsyncIOMotorDatabase,
    query: str | None,
    normalized_tags: list[str] | None,
    formats: list[str] | None = None,
    audio_types: list[str] | None = None,
    sort_field: str | None = None,
    sort_direction: int = -1,
) -> list[dict]:
    filter_: dict = {}
    if query:
        filter_["$text"] = {"$search": query}
    if normalized_tags:
        filter_["tags_normalized"] = {"$all": normalized_tags}
    if formats:
        filter_["format"] = {"$in": formats}
    if audio_types:
        filter_["audio_types"] = {"$in": audio_types}

    mongo_sort_field = SORT_FIELDS.get(sort_field, DEFAULT_SORT_FIELD)
    cursor = db[COLLECTION].find(filter_).sort(mongo_sort_field, sort_direction)
    return await cursor.to_list(length=500)


async def update(db: AsyncIOMotorDatabase, movie_id: str, fields: dict) -> dict | None:
    if not ObjectId.is_valid(movie_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(movie_id)}, {"$set": fields})
    return await db[COLLECTION].find_one({"_id": ObjectId(movie_id)})


async def delete(db: AsyncIOMotorDatabase, movie_id: str) -> bool:
    if not ObjectId.is_valid(movie_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(movie_id)})
    return result.deleted_count > 0


async def archive_deleted(db: AsyncIOMotorDatabase, movie_doc: dict, deleted_by: str) -> None:
    """Logs a deleted movie (serial_number, title, when, who) before the
    document itself is removed from `movies` — see FEATURES.md #29. Once the
    document is gone, its serial_number is no longer taken, so it is
    automatically free for the counter or a manual edit to reuse."""
    await db[DELETED_COLLECTION].insert_one(
        {
            "movie_id": movie_doc["_id"],
            "serial_number": movie_doc.get("serial_number"),
            "title": movie_doc["title"],
            "year": movie_doc.get("year"),
            "format": movie_doc.get("format"),
            "deleted_at": datetime.now(timezone.utc),
            "deleted_by": deleted_by,
        }
    )


async def list_deleted(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db[DELETED_COLLECTION].find().sort("deleted_at", -1)
    return await cursor.to_list(length=1000)
