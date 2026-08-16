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


async def find_all(
    db: AsyncIOMotorDatabase, upcoming_only: bool = False, past_only: bool = False
) -> list[dict]:
    """`upcoming_only` → fremtidige, ældste først (Voldby BIO-programmet).
    `past_only` (feature #130) → allerede afholdte, **nyeste først**, så
    historik-listen viser det seneste øverst og 500-cap'en beholder de nyeste
    frem for de ældste. `upcoming_only` vinder hvis begge er sat."""
    now = datetime.now(timezone.utc)
    if upcoming_only:
        cursor = db[COLLECTION].find({"scheduled_at": {"$gte": now}}).sort("scheduled_at", 1)
    elif past_only:
        cursor = db[COLLECTION].find({"scheduled_at": {"$lt": now}}).sort("scheduled_at", -1)
    else:
        cursor = db[COLLECTION].find({}).sort("scheduled_at", 1)
    return await cursor.to_list(length=500)


async def find_past_ids(db: AsyncIOMotorDatabase, screening_ids: list[str]) -> list[str]:
    """Feature #167 — hvilke af de givne screening-id'er er allerede afholdt
    (scheduled_at i fortiden)? Bruges af reservation_service til at afgøre
    hvilke sæde-reservationer der kan ryddes op, efter en fremvisning er vist."""
    valid_ids = [ObjectId(sid) for sid in screening_ids if ObjectId.is_valid(sid)]
    if not valid_ids:
        return []
    now = datetime.now(timezone.utc)
    cursor = db[COLLECTION].find(
        {"_id": {"$in": valid_ids}, "scheduled_at": {"$lt": now}}, {"_id": 1}
    )
    return [str(doc["_id"]) async for doc in cursor]


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


async def delete_for_title(
    db: AsyncIOMotorDatabase, media_kind: str, title_id: str
) -> int:
    """BUGS.md #43 — removes every screening pointing at a movie/TV show
    that's being deleted. Title/poster are resolved by reference at read
    time (never copied onto the screening), so a screening left behind after
    its title is gone renders as an empty ghost card — including on the
    public, shareable /bio page. Returns how many were removed."""
    field = "movie_id" if media_kind == "movie" else "tv_show_id"
    result = await db[COLLECTION].delete_many({"media_kind": media_kind, field: title_id})
    return result.deleted_count
