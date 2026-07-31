from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "movies"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    collection = db[COLLECTION]
    await collection.create_index([("title", "text"), ("overview", "text")])
    await collection.create_index("tags_normalized")
    await collection.create_index("barcode", unique=True, sparse=True)


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_id(db: AsyncIOMotorDatabase, movie_id: str) -> dict | None:
    if not ObjectId.is_valid(movie_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(movie_id)})


async def find_many(
    db: AsyncIOMotorDatabase, query: str | None, normalized_tags: list[str] | None
) -> list[dict]:
    filter_: dict = {}
    if query:
        filter_["$text"] = {"$search": query}
    if normalized_tags:
        filter_["tags_normalized"] = {"$all": normalized_tags}

    cursor = db[COLLECTION].find(filter_).sort("created_at", -1)
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
