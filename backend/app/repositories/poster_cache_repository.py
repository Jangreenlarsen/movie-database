from datetime import datetime, timezone

from bson import Binary
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

# Feature #153 — permanent lokal cache af TMDb-poster-billeder. Nøglet på
# (size, path), da forskellige størrelser er reelt forskellige TMDb-genererede
# billedfiler, ikke bare en skalering af samme bytes.
COLLECTION = "poster_cache"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[COLLECTION].create_index([("size", 1), ("path", 1)], unique=True)


async def find_one(db: AsyncIOMotorDatabase, size: str, path: str) -> dict | None:
    return await db[COLLECTION].find_one({"size": size, "path": path})


async def insert(db: AsyncIOMotorDatabase, size: str, path: str, content_type: str, data: bytes) -> dict:
    document = {
        "size": size,
        "path": path,
        "content_type": content_type,
        "data": Binary(data),
        "byte_size": len(data),
        "cached_at": datetime.now(timezone.utc),
    }
    try:
        result = await db[COLLECTION].insert_one(document)
        document["_id"] = result.inserted_id
    except DuplicateKeyError:
        # To samtidige første-visninger af samme (size, path) kan begge nå at
        # cache-misse før nogen har skrevet. Den der taber racet bruger bare
        # den vindende skrivning i stedet for at fejle.
        existing = await find_one(db, size, path)
        if existing is not None:
            return existing
        raise
    return document


async def find_all_raw(db: AsyncIOMotorDatabase) -> list[dict]:
    """Unbounded — backer den fulde system-backup (feature #61/#153)."""
    return await db[COLLECTION].find({}).to_list(length=None)
