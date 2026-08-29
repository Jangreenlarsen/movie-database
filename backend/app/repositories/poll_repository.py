from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "polls"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[COLLECTION].create_index("status")


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_id(db: AsyncIOMotorDatabase, poll_id: str) -> dict | None:
    if not ObjectId.is_valid(poll_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(poll_id)})


async def find_all(db: AsyncIOMotorDatabase, status: str | None = None) -> list[dict]:
    query = {"status": status} if status else {}
    return await db[COLLECTION].find(query).sort("created_at", -1).to_list(length=200)


async def upsert_vote(
    db: AsyncIOMotorDatabase, poll_id: str, username: str, candidate_index: int, voted_at: datetime
) -> dict | None:
    """Feature #162 — én aktiv stemme pr. bruger, men brugeren må frit skifte
    mening mens afstemningen er åben. To sekventielle skrivninger (fjern evt.
    eksisterende stemme fra denne bruger, tilføj den nye) frem for én atomisk
    operation — MongoDB har intet indbygget "upsert ind i et array matchet på
    et underfelt"-primitiv. Samme lave, accepterede race-risiko som appens
    øvrige simple array-opdateringer (fx screening_request_repository.
    add_requester) — ikke en bank, et par families husstands-stemmer."""
    if not ObjectId.is_valid(poll_id):
        return None
    await db[COLLECTION].update_one(
        {"_id": ObjectId(poll_id)}, {"$pull": {"votes": {"username": username}}}
    )
    await db[COLLECTION].update_one(
        {"_id": ObjectId(poll_id)},
        {
            "$push": {
                "votes": {"username": username, "candidate_index": candidate_index, "voted_at": voted_at}
            }
        },
    )
    return await find_by_id(db, poll_id)


async def set_status(
    db: AsyncIOMotorDatabase, poll_id: str, status: str, closed_at: datetime | None = None
) -> dict | None:
    if not ObjectId.is_valid(poll_id):
        return None
    fields = {"status": status}
    if closed_at is not None:
        fields["closed_at"] = closed_at
    await db[COLLECTION].update_one({"_id": ObjectId(poll_id)}, {"$set": fields})
    return await find_by_id(db, poll_id)


async def set_scheduled(db: AsyncIOMotorDatabase, poll_id: str, screening_id: str) -> dict | None:
    if not ObjectId.is_valid(poll_id):
        return None
    await db[COLLECTION].update_one(
        {"_id": ObjectId(poll_id)},
        {"$set": {"status": "scheduled", "scheduled_screening_id": screening_id}},
    )
    return await find_by_id(db, poll_id)
