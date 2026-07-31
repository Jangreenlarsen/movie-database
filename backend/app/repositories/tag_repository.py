from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "tags"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[COLLECTION].create_index("normalized", unique=True)


async def find_by_normalized(db: AsyncIOMotorDatabase, normalized: str) -> dict | None:
    return await db[COLLECTION].find_one({"normalized": normalized})


async def insert(db: AsyncIOMotorDatabase, name: str, normalized: str) -> dict:
    document = {"name": name, "normalized": normalized}
    result = await db[COLLECTION].insert_one(document)
    document["_id"] = result.inserted_id
    return document


async def list_all(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db[COLLECTION].find().sort("name", 1)
    return await cursor.to_list(length=1000)
