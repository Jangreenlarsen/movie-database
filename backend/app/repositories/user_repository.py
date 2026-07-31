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
        "rating": False,
    },
}


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[COLLECTION].create_index("username", unique=True)


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_username(db: AsyncIOMotorDatabase, username: str) -> dict | None:
    return await db[COLLECTION].find_one({"username": username})


async def find_by_id(db: AsyncIOMotorDatabase, user_id: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})


async def update_settings(db: AsyncIOMotorDatabase, user_id: str, settings: dict) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(user_id)}, {"$set": {"settings": settings}})
    return await db[COLLECTION].find_one({"_id": ObjectId(user_id)})
