from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "seat_reservations"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db[COLLECTION].create_index("screening_id")
    await db[COLLECTION].create_index("status")
    await db[COLLECTION].create_index("reserved_by")
    # Feature #133 — race-sikkerhed (samme klasse som BUGS.md #44): kun ÉN
    # reservation pr. (sæde, fremvisning) må findes. Et globalt admin-hold
    # gemmes med `screening_id: None`, så (seat_id, None) er unik → højst ét
    # globalt hold pr. sæde, og et globalt hold kolliderer ikke i selve
    # indexet med en fremvisnings-specifik reservation for samme sæde
    # (forskellig screening_id) — den kombination blokeres i stedet i
    # service-laget (`find_seat_conflict`). Afviste/annullerede reservationer
    # SLETTES frem for at markeres, så der er ingen status i nøglen og intet
    # partial-filter nødvendigt.
    await db[COLLECTION].create_index(
        [("seat_id", 1), ("screening_id", 1)],
        unique=True,
        name="uniq_seat_per_screening",
    )


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_id(db: AsyncIOMotorDatabase, reservation_id: str) -> dict | None:
    if not ObjectId.is_valid(reservation_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(reservation_id)})


async def find_for_screening_context(db: AsyncIOMotorDatabase, screening_id: str) -> list[dict]:
    """Alle reservationer der påvirker sædekortet for én fremvisning: dens
    egne fremvisnings-specifikke reservationer + samtlige globale hold."""
    cursor = db[COLLECTION].find(
        {"$or": [{"screening_id": screening_id}, {"scope": "global"}]}
    )
    return await cursor.to_list(length=500)


async def find_seat_conflict(
    db: AsyncIOMotorDatabase, seat_id: str, screening_id: str
) -> dict | None:
    """Findes der allerede en reservation der blokerer `seat_id` for denne
    fremvisning? Dvs. enten en fremvisnings-specifik for samme (sæde,
    fremvisning) eller et globalt hold på sædet."""
    return await db[COLLECTION].find_one(
        {
            "seat_id": seat_id,
            "$or": [{"screening_id": screening_id}, {"scope": "global"}],
        }
    )


async def find_any_for_seat(db: AsyncIOMotorDatabase, seat_id: str) -> dict | None:
    """Én vilkårlig reservation på sædet, uanset fremvisning — bruges når et
    *globalt* hold oprettes, som konflikter med enhver eksisterende reservation."""
    return await db[COLLECTION].find_one({"seat_id": seat_id})


async def find_all(
    db: AsyncIOMotorDatabase, status: str | None = None, screening_id: str | None = None
) -> list[dict]:
    filter_: dict = {}
    if status:
        filter_["status"] = status
    if screening_id:
        filter_["screening_id"] = screening_id
    cursor = db[COLLECTION].find(filter_).sort("created_at", -1)
    return await cursor.to_list(length=500)


async def find_for_user(db: AsyncIOMotorDatabase, username: str) -> list[dict]:
    cursor = db[COLLECTION].find({"reserved_by": username}).sort("created_at", -1)
    return await cursor.to_list(length=500)


async def update(db: AsyncIOMotorDatabase, reservation_id: str, fields: dict) -> dict | None:
    if not ObjectId.is_valid(reservation_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(reservation_id)}, {"$set": fields})
    return await db[COLLECTION].find_one({"_id": ObjectId(reservation_id)})


async def delete(db: AsyncIOMotorDatabase, reservation_id: str) -> bool:
    if not ObjectId.is_valid(reservation_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(reservation_id)})
    return result.deleted_count > 0


async def delete_for_screening(db: AsyncIOMotorDatabase, screening_id: str) -> int:
    """Feature #133 — når en fremvisning slettes, forsvinder dens
    reservationer med den (globale hold, der ikke hører til nogen fremvisning,
    røres ikke). Returnerer antal fjernede."""
    result = await db[COLLECTION].delete_many({"screening_id": screening_id})
    return result.deleted_count


async def find_distinct_screening_ids(db: AsyncIOMotorDatabase) -> list[str]:
    """Feature #167 — alle distinkte screening_id'er der aktuelt har mindst
    én reservation. Ekskluderer globale hold (screening_id: None) implicit,
    da `distinct` ikke medtager None-værdier for et felt der forespørges
    sådan her — men filteret er alligevel eksplicit for at gøre hensigten
    klar (aldrig ramme globale hold)."""
    return await db[COLLECTION].distinct("screening_id", {"screening_id": {"$ne": None}})


async def delete_for_screenings(db: AsyncIOMotorDatabase, screening_ids: list[str]) -> int:
    """Feature #167 — som delete_for_screening, men for flere fremvisninger
    på én gang (den afholdte-oprydning tjekker typisk flere ad gangen)."""
    if not screening_ids:
        return 0
    result = await db[COLLECTION].delete_many({"screening_id": {"$in": screening_ids}})
    return result.deleted_count
