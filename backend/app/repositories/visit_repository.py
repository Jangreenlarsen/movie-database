from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "visits"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    collection = db[COLLECTION]
    await collection.create_index("at")
    await collection.create_index("page")
    await collection.create_index("username")
    await collection.create_index("kind")


async def insert(db: AsyncIOMotorDatabase, document: dict) -> None:
    await db[COLLECTION].insert_one(document)


async def find_all(db: AsyncIOMotorDatabase) -> list[dict]:
    """Feature #125 — hele besøgs-historikken hentes og aggregeres i Python
    (samme mønster som `movie_service.get_stats`, der itererer dokumenter og
    tæller med `Counter`). Bevidst valg frem for en Mongo-aggregations-pipeline:
    testsuiten kører mod mongomock, hvis `$group`/`$dateToString`-understøttelse
    er ufuldstændig — en ren Python-aggregering er hermetisk testbar og rigelig
    til et hjemme-biblioteks besøgsvolumen."""
    cursor = db[COLLECTION].find({})
    return [doc async for doc in cursor]


async def count(db: AsyncIOMotorDatabase) -> int:
    return await db[COLLECTION].count_documents({})
