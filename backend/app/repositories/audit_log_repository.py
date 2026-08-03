from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "audit_log"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[COLLECTION].create_index("created_at")


async def insert(db: AsyncIOMotorDatabase, actor: str, action: str, detail: str | None) -> dict:
    document = {
        "actor": actor,
        "action": action,
        "detail": detail,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db[COLLECTION].insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def list_paginated(db: AsyncIOMotorDatabase, skip: int, limit: int) -> list[dict]:
    cursor = db[COLLECTION].find().sort("created_at", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


async def count(db: AsyncIOMotorDatabase) -> int:
    return await db[COLLECTION].count_documents({})
