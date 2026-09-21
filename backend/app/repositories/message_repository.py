"""Beskeder fra admin til brugerne (feature #100)."""

from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "messages"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    collection = db[COLLECTION]
    # Afsender-oversigten viser nyeste øverst.
    await collection.create_index("created_at")
    # Indbakke-opslaget filtrerer på modtagerens id og på om beskeden er
    # læst — begge felter ligger i samme array-element, så et sammensat
    # index på de to stier er det der rent faktisk bruges.
    await collection.create_index([("recipients.user_id", 1), ("recipients.read_at", 1)])


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_id(db: AsyncIOMotorDatabase, message_id: str) -> dict | None:
    if not ObjectId.is_valid(message_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(message_id)})


async def list_all(db: AsyncIOMotorDatabase) -> list[dict]:
    """Alle sendte beskeder, nyeste øverst — afsender-oversigten."""
    cursor = db[COLLECTION].find({}).sort("created_at", -1)
    return await cursor.to_list(length=None)


async def list_unread_for_user(db: AsyncIOMotorDatabase, user_id: str) -> list[dict]:
    """Beskeder brugeren endnu ikke har lukket, ældste først.

    `$elemMatch` frem for to separate `recipients.`-betingelser: uden den
    ville en besked hvor *en anden* modtager er ulæst også matche, fordi de
    to betingelser da kan opfyldes af hvert sit element i arrayet."""
    cursor = db[COLLECTION].find(
        {"recipients": {"$elemMatch": {"user_id": user_id, "read_at": None}}}
    ).sort("created_at", 1)
    return await cursor.to_list(length=None)


async def mark_read(db: AsyncIOMotorDatabase, message_id: str, user_id: str) -> bool:
    """Markerer én modtagers eksemplar som læst. Returnerer False hvis
    beskeden ikke findes, eller brugeren ikke er blandt modtagerne.

    Punktum-sti-`$set` med positional operator, aldrig en read-modify-write
    af hele modtagerlisten (CLAUDE.md regel 16): to brugere der lukker den
    samme rundsendte besked samtidig må ikke kunne overskrive hinandens
    markering."""
    if not ObjectId.is_valid(message_id):
        return False
    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(message_id), "recipients.user_id": user_id},
        {"$set": {"recipients.$.read_at": datetime.now(timezone.utc)}},
    )
    return result.matched_count > 0


async def mark_all_read(db: AsyncIOMotorDatabase, user_id: str) -> int:
    """Markerer ALLE brugerens ulæste beskeder som læst i ét kald (feature
    #226) — "Ryd alle" i Indstillinger → Beskeder, i stedet for ét kald pr.
    besked (kan være tusindvis efter lang tids fravær).

    Positional `$` (ikke `$[elem]`/`array_filters` — mongomock, som hele
    testsuiten kører mod, understøtter det ikke endnu) rammer for HVERT
    matchet dokument det første element der opfylder selve query'ens
    `$elemMatch`, dvs. netop brugerens eget — en bruger optræder aldrig to
    gange i samme beskeds modtagerliste, så det er entydigt. Samme
    punktum-sti-`$set`-princip som `mark_read` ovenfor, blot som
    `update_many`, så en anden modtagers markering aldrig kan overskrives."""
    now = datetime.now(timezone.utc)
    result = await db[COLLECTION].update_many(
        {"recipients": {"$elemMatch": {"user_id": user_id, "read_at": None}}},
        {"$set": {"recipients.$.read_at": now}},
    )
    return result.modified_count


async def delete(db: AsyncIOMotorDatabase, message_id: str) -> bool:
    if not ObjectId.is_valid(message_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(message_id)})
    return result.deleted_count > 0
