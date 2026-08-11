"""Den fælles D#-nummerserie for digitale udgaver (feature #93).

Film og TV-serier har hver sin fysiske serie (`movie_serial`/`tv_show_serial`),
men deler **én** digital serie — Jans valg 2026-08-08. Begrundelsen er at et
D#-nummer så altid peger på præcis én ting, ligesom M# og T# gør hver for sig;
to adskilte D#-serier ville give to forskellige udgaver der begge hed D#0001,
netop den tvetydighed M#/T#-opdelingen fjernede.

At serien er delt på tværs af to collections er grunden til at den bor her og
ikke i en af dem: tildelingen skal kunne se begge, hvilket hverken
`movie_repository` eller `tv_show_repository` kan alene.
"""

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

COUNTERS_COLLECTION = "counters"
SERIAL_COUNTER_ID = "digital_serial"
DEFAULT_SERIAL_CONFIG = {"next_value": 1, "increment": 1}
MAX_SERIAL_ASSIGN_ATTEMPTS = 10_000

# Bevidst hardkodet frem for importeret fra de to repositories: de importerer
# ikke dette modul, og at gå den anden vej ville lave en cyklus for en oplysning
# der er to konstante strenge.
MOVIE_COLLECTION = "movies"
TV_SHOW_COLLECTION = "tv_shows"

DIGITAL = "Digital"

logger = logging.getLogger("moviedb")


async def _ensure_config(db: AsyncIOMotorDatabase) -> dict:
    doc = await db[COUNTERS_COLLECTION].find_one({"_id": SERIAL_COUNTER_ID})
    if doc is None:
        doc = {"_id": SERIAL_COUNTER_ID, **DEFAULT_SERIAL_CONFIG}
        await db[COUNTERS_COLLECTION].insert_one(doc)
    return doc


async def _is_taken(db: AsyncIOMotorDatabase, candidate: int) -> bool:
    """Er nummeret allerede brugt af en digital post i én af de to
    collections? Det unikke index kan kun håndhæve entydighed *inden for* en
    collection, så krydset mellem film og serier skal tjekkes her."""
    for collection in (MOVIE_COLLECTION, TV_SHOW_COLLECTION):
        existing = await db[collection].find_one(
            {"serial_number": candidate, "media_type": DIGITAL}, {"_id": 1}
        )
        if existing is not None:
            return True
    return False


async def next_serial_number(db: AsyncIOMotorDatabase) -> int:
    """Samme race-sikre "spring optagne over"-tilgang som de to fysiske
    serier (se movie_repository.next_serial_number), udvidet til at tjekke
    begge collections."""
    for _ in range(MAX_SERIAL_ASSIGN_ATTEMPTS):
        config = await _ensure_config(db)
        increment = config.get("increment", DEFAULT_SERIAL_CONFIG["increment"])

        before = await db[COUNTERS_COLLECTION].find_one_and_update(
            {"_id": SERIAL_COUNTER_ID},
            {"$inc": {"next_value": increment}},
            return_document=ReturnDocument.BEFORE,
        )
        candidate = before["next_value"]

        if not await _is_taken(db, candidate):
            return candidate

    raise RuntimeError("Kunne ikke finde et ledigt digitalt serienummer")


async def find_series_holder(
    db: AsyncIOMotorDatabase,
    media_type: str | None,
    serial_number: int,
    physical_collection: str,
    exclude_id=None,
) -> tuple[str, dict] | None:
    """BUGS.md #56 — den post der pt. holder `serial_number` i *samme serie*
    som `media_type`, eller None.

    Serie-bevidstheden er hele pointen: et serienummer er kun entydigt inden
    for sin egen serie (M/T/D), så et byt-plads-opslag der kun matcher på tallet
    ville kunne gribe en post fra en *anden* serie (fx en digital D#10 når man
    redigerer en fysisk M#16). Digitale poster deles på tværs af begge
    collections (samme grund som `_is_taken`); fysiske/uklassificerede tælles kun
    i deres egen collection og udelukker digitale.

    Returnerer `(collection_name, doc)`, så en swap kan skrive tilbage i den
    rigtige collection — også når en digital film bytter med en digital TV-serie.
    """
    if media_type == DIGITAL:
        for collection in (MOVIE_COLLECTION, TV_SHOW_COLLECTION):
            doc = await db[collection].find_one(
                {"serial_number": serial_number, "media_type": DIGITAL}
            )
            if doc is not None and doc["_id"] != exclude_id:
                return collection, doc
        return None

    # Fysisk eller uklassificeret: kun den angivne collection, og aldrig en
    # digital post — `$ne` frem for `"Fysisk"`-lighed, så en gammel post uden
    # medietype (talt med som fysisk) også kan bytte plads.
    doc = await db[physical_collection].find_one(
        {"serial_number": serial_number, "media_type": {"$ne": DIGITAL}}
    )
    if doc is not None and doc["_id"] != exclude_id:
        return physical_collection, doc
    return None


async def set_serial(
    db: AsyncIOMotorDatabase, collection_name: str, doc_id, serial_number: int
) -> None:
    """Sætter et serienummer i en vilkårlig af de to collections — bruges af
    byt-plads-omnummereringen, som (for den delte digitale serie) kan skulle
    skrive i den *anden* collection end den redigerede post."""
    await db[collection_name].update_one(
        {"_id": doc_id}, {"$set": {"serial_number": serial_number}}
    )


async def backfill(db: AsyncIOMotorDatabase, collection_name: str) -> int:
    """Feature #93 — giver digitale poster et D#-nummer.

    To grupper rettes, og begge kriterier er valgt så migreringen er
    idempotent (den må køre ved hver opstart uden at omnummerere noget):

    1. Digitale poster helt uden nummer. Enten oprettet før digitale fik
       numre, eller ryddet af feature #92's migrering, som fjernede dem
       igen fordi reglen dengang var "kun fysiske nummereres".
    2. Digitale poster hvis nummer kolliderer med en *fysisk* post i samme
       collection. Det er poster fra før feature #92 overhovedet blev
       udrullet: deres nummer stammer fra den fysiske serie og hører ikke
       hjemme i D#-rækken. Efter omnummereringen kolliderer de ikke længere,
       så kriteriet holder op med at være opfyldt.

    En digital post med et nummer der *ikke* kolliderer, får lov at beholde
    det. Nummeret er måske tildelt fra den fysiske serie engang, men det er
    stabilt, entydigt og kan stå skrevet ned — at omnummerere det ville være
    en større gene end den kosmetiske uorden det retter.
    """
    collection = db[collection_name]
    assigned = 0

    cursor = collection.find(
        {"media_type": DIGITAL, "serial_number": {"$exists": False}}, {"_id": 1}
    ).sort("created_at", 1)
    async for doc in cursor:
        collection_update = {"$set": {"serial_number": await next_serial_number(db)}}
        await collection.update_one({"_id": doc["_id"]}, collection_update)
        assigned += 1

    # Kollisioner med den fysiske serie i samme collection.
    cursor = collection.find(
        {"media_type": DIGITAL, "serial_number": {"$exists": True}}, {"_id": 1, "serial_number": 1}
    ).sort("created_at", 1)
    async for doc in cursor:
        clash = await collection.find_one(
            {
                "serial_number": doc["serial_number"],
                "media_type": {"$ne": DIGITAL},
                "_id": {"$ne": doc["_id"]},
            },
            {"_id": 1},
        )
        if clash is None:
            continue
        await collection.update_one(
            {"_id": doc["_id"]}, {"$set": {"serial_number": await next_serial_number(db)}}
        )
        assigned += 1

    if assigned:
        logger.info(
            "%s: tildelte D#-nummer til %s digitale poster (feature #93)",
            collection_name,
            assigned,
        )
    return assigned
