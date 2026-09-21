from motor.motor_asyncio import AsyncIOMotorDatabase

# Feature #225 — admin-tilpassede besked-skabeloner. Ét dokument pr.
# redigeret besked-type, nøglet på selve besked-typens nøgle (fx
# "wishlist_moved", se message_service.TEMPLATE_DEFS) som `_id` — ingen
# separat generet id nødvendig, og et opslag på én bestemt type er dermed
# et direkte `_id`-opslag. Kun typer der RENT FAKTISK er tilpasset har et
# dokument her; en manglende `_id` betyder "brug kode-standarden" (samme
# "override eller kode-standard"-mønster som `system_settings_repository`
# allerede bruger til eksterne API-nøgler).
COLLECTION = "message_templates"


async def find_all(db: AsyncIOMotorDatabase) -> dict[str, dict]:
    """Returnerer `{key: template_doc}` for hver tilpasset besked-type.
    Kaldes ÉN gang pr. notify_*-kald i message_service.py (aldrig pr.
    modtager i en løkke) — se disses egne kommentarer."""
    docs = await db[COLLECTION].find({}).to_list(length=None)
    return {doc["_id"]: doc for doc in docs}


async def find_one(db: AsyncIOMotorDatabase, key: str) -> dict | None:
    return await db[COLLECTION].find_one({"_id": key})


async def upsert(db: AsyncIOMotorDatabase, key: str, fields: dict) -> dict:
    """`fields` indeholder KUN de felter admin rent faktisk har sat
    (subject/body/headline/tagline/accent/cta_label — aldrig alle seks for
    en besked-type uden HTML-udgave). `$set` i stedet for en hel
    dokument-erstatning, så en fremtidig delvis opdatering ikke nulstiller
    felter der ikke var med i det pågældende kald."""
    await db[COLLECTION].update_one({"_id": key}, {"$set": fields}, upsert=True)
    return await find_one(db, key)


async def delete(db: AsyncIOMotorDatabase, key: str) -> bool:
    """Nulstiller én besked-type til kode-standarden ved simpelthen at
    fjerne dens override-dokument. Returnerer `False` hvis typen ikke var
    tilpasset i forvejen (allerede på standarden — kaldende service-lag
    afgør om det skal give en fejl eller bare være et stille no-op)."""
    result = await db[COLLECTION].delete_one({"_id": key})
    return result.deleted_count > 0


async def find_all_raw(db: AsyncIOMotorDatabase) -> list[dict]:
    """Backer den fulde system-backup (feature #61/#225, CLAUDE.md regel
    20) — enhver admin-tilpasset besked-ordlyd skal overleve en
    backup/restore-cyklus ligesom alt andet admin-konfigureret."""
    return await db[COLLECTION].find({}).to_list(length=None)


async def replace_all(db: AsyncIOMotorDatabase, documents: list[dict]) -> None:
    """Wholesale replace — bruges kun af system-restore (feature #61/#225).
    Ikke transaktionel; se movie_repository.replace_all's docstring for
    den identiske begrundelse."""
    await db[COLLECTION].delete_many({})
    if documents:
        await db[COLLECTION].insert_many(documents)
