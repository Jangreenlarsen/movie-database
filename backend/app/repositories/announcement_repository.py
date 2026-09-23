from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

# Feature #228 — køen til den samlede opdatering: én post pr. film/serie der
# venter på at blive nævnt i den næste samlede besked til alle brugere.
COLLECTION = "pending_announcements"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    # Samme titel må aldrig stå i køen to gange — fx hvis den gemmes igen med
    # "samlet opdatering" valgt, eller to faner når at lægge den i kø samtidig.
    await db[COLLECTION].create_index(
        [("media_kind", 1), ("item_id", 1)],
        unique=True,
        name="uniq_announcement_per_item",
    )
    await db[COLLECTION].create_index("created_at")


async def insert_if_absent(db: AsyncIOMotorDatabase, document: dict) -> bool:
    """True hvis titlen blev lagt i køen, False hvis den allerede stod der.
    Race-sikkert via det unikke index frem for et forudgående opslag."""
    try:
        await db[COLLECTION].insert_one(document)
    except DuplicateKeyError:
        return False
    return True


async def find_all(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db[COLLECTION].find({}).sort("created_at", 1)
    return await cursor.to_list(length=None)


async def find_by_id(db: AsyncIOMotorDatabase, announcement_id: str) -> dict | None:
    if not ObjectId.is_valid(announcement_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(announcement_id)})


async def delete(db: AsyncIOMotorDatabase, announcement_id: str) -> bool:
    if not ObjectId.is_valid(announcement_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(announcement_id)})
    return result.deleted_count > 0


async def delete_many_by_ids(db: AsyncIOMotorDatabase, ids: list[ObjectId]) -> int:
    """Sletter præcis de angivne poster — aldrig "alt i køen", så en titel
    der lægges i kø mens en afsendelse er i gang, bliver stående."""
    if not ids:
        return 0
    result = await db[COLLECTION].delete_many({"_id": {"$in": ids}})
    return result.deleted_count
