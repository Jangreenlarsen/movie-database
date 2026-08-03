from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "screenings"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[COLLECTION].create_index("scheduled_at")


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_id(db: AsyncIOMotorDatabase, screening_id: str) -> dict | None:
    if not ObjectId.is_valid(screening_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(screening_id)})


async def find_all(db: AsyncIOMotorDatabase, upcoming_only: bool = False) -> list[dict]:
    filter_ = {"scheduled_at": {"$gte": datetime.now(timezone.utc)}} if upcoming_only else {}
    cursor = db[COLLECTION].find(filter_).sort("scheduled_at", 1)
    return await cursor.to_list(length=500)


async def update(db: AsyncIOMotorDatabase, screening_id: str, fields: dict) -> dict | None:
    if not ObjectId.is_valid(screening_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(screening_id)}, {"$set": fields})
    return await db[COLLECTION].find_one({"_id": ObjectId(screening_id)})


async def delete(db: AsyncIOMotorDatabase, screening_id: str) -> bool:
    if not ObjectId.is_valid(screening_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(screening_id)})
    return result.deleted_count > 0
