from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

COLLECTION = "movies"
COUNTERS_COLLECTION = "counters"
SERIAL_COUNTER_ID = "movie_serial"

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


async def next_serial_number(db: AsyncIOMotorDatabase) -> int:
    """Atomically incremented, race-safe even under concurrent creates."""
    counter = await db[COUNTERS_COLLECTION].find_one_and_update(
        {"_id": SERIAL_COUNTER_ID},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return counter["value"]


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
