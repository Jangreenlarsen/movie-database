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
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

COUNTERS_COLLECTION = "counters"
SERIAL_COUNTER_ID = "digital_serial"
# Feature #131 — én fælles til/fra for genbrug af frigjorte serienumre, gældende
# for alle tre serier (M/T/D). Bor her, fordi både movie_ og tv_show_repository
# allerede importerer dette modul (og det importerer ingen af dem), så flaget
# kan læses ét sted uden en cirkulær import.
REUSE_FLAG_ID = "serial_reuse"
DEFAULT_SERIAL_CONFIG = {"next_value": 1, "increment": 1}
MAX_SERIAL_ASSIGN_ATTEMPTS = 10_000

# Feature #139 — den delte 5000+-pulje. Poster hvis ejer ikke er en
# jan/lis-variant og som ikke er oprettet af en admin, får serienummer herfra
# (Jans valg: ÉN fælles serie på tværs af film/TV/digital, ikke tre). Bor her
# af samme grund som D#-serien: tildelingen skal kunne se begge collections.
OTHER_SERIAL_COUNTER_ID = "other_serial"
OTHER_SERIAL_START = 5000

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


# --- Feature #131: genbrug af frigjorte numre -------------------------------


async def is_reuse_enabled(db: AsyncIOMotorDatabase) -> bool:
    doc = await db[COUNTERS_COLLECTION].find_one({"_id": REUSE_FLAG_ID})
    return bool(doc and doc.get("enabled", False))


async def set_reuse_enabled(db: AsyncIOMotorDatabase, enabled: bool) -> None:
    await db[COUNTERS_COLLECTION].update_one(
        {"_id": REUSE_FLAG_ID}, {"$set": {"enabled": bool(enabled)}}, upsert=True
    )


MAX_FREE_NUMBERS = 100
"""Jan, 2026-08-22: "vi skal også have en max størrelse på hvor mange nr vi
holder i de lister over genbrugs nr. eks. hvis en adm opretter en film med
et nr på 50000, så vil den genbrugs list indholde alle nr fra den sidste ca
omkring 500 til 49999, det giver ikke mening" — uden et loft ville et enkelt
usædvanligt højt nummer et sted i serien få `gaps()` til at regne (og
frontend til at vise) titusindvis af "ledige" numre. Kun de LAVESTE tælles
med (loopet i `gaps()` stopper tidligt), da det er dem `next_serial_number`
rent faktisk genbruger først, og dem en admin realistisk vil kigge efter i
Indstillinger-visningen. Jans valg: "jeg tænker max på 100"."""


def gaps(taken: set[int], next_value: int = 1, increment: int = 1) -> list[int]:
    """De frigjorte numre = huller i det faktisk brugte interval.

    BUGS.md #83: øvre grænse er IKKE `max(taken)` alene, men det højeste af
    `max(taken)` og det sidste nummer tælleren reelt har uddelt
    (`next_value - increment`). Sletter man de øverste numre i serien (fx
    1-6 → slet 5,6), falder `max(taken)` til 4, men tælleren står stadig på
    7 — uden denne udvidelse ville 5,6 slet ikke blive genkendt som ledige
    FØR endnu en post et sted fik et højere nummer end 6 og dermed
    tilfældigvis trak dem "ind i" intervallet igen (Jans observerede
    symptom: 5,6 dukkede først op som ledige, efter den næste film fik
    #7 i stedet for at genbruge #5). Tælleren rører vi bevidst IKKE ved
    sletning — `next_value` er den eneste kilde til "højeste nogensinde
    uddelte nummer", og skal blive ved med at stige monotont for at forblive
    kollisionsfri; det er selve DENNE funktions definition af "ledig" der
    var for snæver, ikke tælleren der var forkert.

    Tal under det laveste brugte tælles bevidst stadig ikke med, så en
    flyttet start-værdi (fx start på 100) ikke pludselig udpeger 1-99 som
    ledige.

    BUGS.md #86: loopet stopper tidligt så snart `MAX_FREE_NUMBERS` (100,
    laveste først) er fundet — ikke kun en efterfølgende afkortning af en
    allerede fuldt udregnet liste, men et reelt tidligt stop, så et enkelt
    usædvanligt højt nummer et sted i serien ikke får funktionen til at
    iterere titusindvis af numre den alligevel aldrig ville vise eller
    genbruge."""
    if not taken:
        return []
    highest_ever_assigned = max(max(taken), next_value - increment)
    free: list[int] = []
    for n in range(min(taken), highest_ever_assigned + 1):
        if n not in taken:
            free.append(n)
            if len(free) >= MAX_FREE_NUMBERS:
                break
    return free


async def _taken_digital_numbers(db: AsyncIOMotorDatabase) -> set[int]:
    taken: set[int] = set()
    for collection in (MOVIE_COLLECTION, TV_SHOW_COLLECTION):
        # Feature #139 — 5000+-pulje-numre hører ikke til D#-serien og udelades
        # her, ellers ville D#-genbrugets "huller" (og "Ledige numre"-oversigten)
        # række helt op til 5000+ og udpege tusindvis af falske ledige numre.
        cursor = db[collection].find(
            {
                "media_type": DIGITAL,
                "serial_number": {"$exists": True, "$lt": OTHER_SERIAL_START},
            },
            {"serial_number": 1},
        )
        async for doc in cursor:
            number = doc.get("serial_number")
            if isinstance(number, int):
                taken.add(number)
    return taken


async def _ensure_other_config(db: AsyncIOMotorDatabase) -> dict:
    doc = await db[COUNTERS_COLLECTION].find_one({"_id": OTHER_SERIAL_COUNTER_ID})
    if doc is None:
        doc = {"_id": OTHER_SERIAL_COUNTER_ID, "next_value": OTHER_SERIAL_START, "increment": 1}
        await db[COUNTERS_COLLECTION].insert_one(doc)
    return doc


async def _is_other_taken(db: AsyncIOMotorDatabase, candidate: int) -> bool:
    """Er 5000+-nummeret allerede brugt af NOGEN post? Puljen er fælles på tværs
    af film/TV og fysisk/digital, så tjekket ignorerer media_type (i modsætning
    til `_is_taken`, der kun ser på digitale)."""
    for collection in (MOVIE_COLLECTION, TV_SHOW_COLLECTION):
        if await db[collection].find_one({"serial_number": candidate}, {"_id": 1}) is not None:
            return True
    return False


async def bump_counters_past(db: AsyncIOMotorDatabase, documents: list[dict]) -> None:
    """BUGS.md #103 — efter en biblioteks-import: flyt D#-tælleren forbi det
    højeste importerede digitale nummer og 5000+-tælleren forbi det højeste
    5000+-nummer, hver i sin egen serie (film og serier under ét, ligesom
    tællerne selv). Uden dette virkede tildelingen stadig — den springer
    optagne numre over — men første nye post skulle i værste fald prøve sig
    igennem hvert eneste importerede nummer ét for ét."""
    digital = [
        doc["serial_number"]
        for doc in documents
        if isinstance(doc.get("serial_number"), int)
        and doc.get("media_type") == DIGITAL
        and doc["serial_number"] < OTHER_SERIAL_START
    ]
    other = [
        doc["serial_number"]
        for doc in documents
        if isinstance(doc.get("serial_number"), int) and doc["serial_number"] >= OTHER_SERIAL_START
    ]
    if digital:
        config = await _ensure_config(db)
        if config.get("next_value", 1) <= max(digital):
            await db[COUNTERS_COLLECTION].update_one(
                {"_id": SERIAL_COUNTER_ID}, {"$set": {"next_value": max(digital) + 1}}
            )
    if other:
        config = await _ensure_other_config(db)
        if config.get("next_value", OTHER_SERIAL_START) <= max(other):
            await db[COUNTERS_COLLECTION].update_one(
                {"_id": OTHER_SERIAL_COUNTER_ID}, {"$set": {"next_value": max(other) + 1}}
            )


async def next_other_serial_number(db: AsyncIOMotorDatabase) -> int:
    """Feature #139 — næste ledige nummer fra den delte 5000+-pulje. Tæller kun
    opad fra 5000 (ingen genbrug — bevidst adskilt fra #131's M/T/D-genbrug), med
    samme race-sikre "spring optagne over"-tilgang som de øvrige serier."""
    for _ in range(MAX_SERIAL_ASSIGN_ATTEMPTS):
        config = await _ensure_other_config(db)
        increment = config.get("increment", 1)
        before = await db[COUNTERS_COLLECTION].find_one_and_update(
            {"_id": OTHER_SERIAL_COUNTER_ID},
            {"$inc": {"next_value": increment}},
            return_document=ReturnDocument.BEFORE,
        )
        candidate = before["next_value"]
        if not await _is_other_taken(db, candidate):
            return candidate
    raise RuntimeError("Kunne ikke finde et ledigt 5000+-serienummer")


async def free_serial_numbers(db: AsyncIOMotorDatabase) -> list[int]:
    """De ledige (frigjorte) D#-numre, laveste først."""
    config = await _ensure_config(db)
    taken = await _taken_digital_numbers(db)
    return gaps(taken, config.get("next_value", 1), config.get("increment", 1))


async def _next_from_counter(db: AsyncIOMotorDatabase) -> int:
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


async def next_serial_number(db: AsyncIOMotorDatabase) -> int:
    """Feature #131 — er genbrug slået til og findes der et frigjort D#-nummer,
    genbruges det laveste før tælleren rykker videre. Ellers (eller uden huller)
    som hidtil fra tælleren."""
    if await is_reuse_enabled(db):
        free = await free_serial_numbers(db)
        if free:
            return free[0]
    return await _next_from_counter(db)


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
    """Feature #93 — giver digitale poster uden et nummer et D#-nummer.

    Retter kun ÉN ting, og gør det idempotent (kører ved hver opstart uden
    at omnummerere noget der allerede er korrekt): digitale poster helt uden
    serienummer. Enten oprettet før digitale fik numre, eller ryddet af
    feature #92's migrering, som dengang fjernede dem igen fordi reglen var
    "kun fysiske nummereres".

    BUGS.md #88 (Jan: "selv om jeg reset D# serie til at starte ved 1 så
    hvis jeg opdatere portal, så starter de igen ved sidste nr som M# serie
    slutter ved" — en ALVORLIG regression): denne funktion havde tidligere
    EN ANDEN gren, der reassignerede ethvert digitalt nummer som "kolliderede"
    med en fysisk post i samme collection. Den gren gav mening FØR M#/T#/D#-
    opdelingen var fuldt indfaset (et digitalt nummer der bogstaveligt var
    arvet fra den fysiske serie, jf. feature #92/#93). Men efter feature
    #188s omnummerering (som bevidst giver D#-serien lave, rene 1..N-numre)
    er det HELT NORMALT og TILSIGTET at fx D#5 og M#5 begge findes samtidigt
    — det er selve pointen med adskilte, præfiksede serier (M#/T#/D# må
    gerne overlappe numerisk, præfikset gør dem entydige). Den gamle
    "kollision"-gren fejltolkede derfor EVERY korrekt lavt D#-nummer som en
    fejl der skulle rettes, og omnummererede dem alle sammen VÆK igen ved
    hver eneste app-genstart — hvilket i praksis gjorde #188s rettelse
    usynlig efter det allerførste "Opdatér"-klik. Grenen er fjernet helt;
    der er intet tilbage der reelt har brug for den (al historisk data fra
    før #93 er enten allerede migreret, eller efterfølgende omnummereret af
    #188)."""
    collection = db[collection_name]
    assigned = 0

    cursor = collection.find(
        {"media_type": DIGITAL, "serial_number": {"$exists": False}}, {"_id": 1}
    ).sort("created_at", 1)
    async for doc in cursor:
        collection_update = {"$set": {"serial_number": await _next_from_counter(db)}}
        await collection.update_one({"_id": doc["_id"]}, collection_update)
        assigned += 1

    if assigned:
        logger.info(
            "%s: tildelte D#-nummer til %s digitale poster (feature #93)",
            collection_name,
            assigned,
        )
    return assigned


# Numre langt over 5000+-puljen (OTHER_SERIAL_START) og enhver realistisk
# D#-værdi — brugt som et midlertidigt, garanteret ledigt "parkerings"-
# område under renumber_from_one nedenfor.
_RENUMBER_TEMP_OFFSET = 1_000_000


async def renumber_from_one(db: AsyncIOMotorDatabase) -> int:
    """Feature #188 (Jan, 2026-08-21, efter BUGS.md #81's årsag blev
    forklaret — feature #93s migrering bevarede bevidst en digital posts
    arvede, før-D#-nummer i stedet for at nulstille den til 1, hvilket
    permanent efterlod numrene 1-162 ubrugte: "Nulstil til at starte fra
    1"). Engangs-omnummerering af ALLE eksisterende digitale poster til en
    ren, sammenhængende D#-serie fra 1, i deres oprettelses-rækkefølge på
    tværs af begge collections (samme rækkefølge-princip som `backfill`
    ovenfor). Kaldes udelukkende eksplicit af en admin
    (`POST /api/settings/serial-number/renumber-digital`) — ALDRIG
    automatisk ved opstart, i modsætning til `backfill`.

    RØRER ALDRIG fysiske (M#/T#) poster (Jans eksplicitte krav: "vi på
    ingen tidspunkt må røre ved M# serie da de er taget i brug") — kun
    dokumenter med `media_type: Digital` forespørges eller opdateres
    overhovedet. Rører heller ikke 5000+-puljens numre (`OTHER_SERIAL_START`)
    — de er en helt separat, delt serie på tværs af alle medietyper.

    To omgange i stedet for én lige-til-den-endelige-værdi: det unikke
    `(serial_number, media_type)`-index håndhæver entydighed pr. collection,
    så en posts NYE nummer (fx 1) kunne ellers midlertidigt kollidere med en
    ANDEN, endnu-ikke-omnummereret posts GAMLE nummer (som også kunne være
    1, hvis rækkefølgen tilfældigvis ramte den situation). Alle poster
    flyttes derfor først til et garanteret ledigt midlertidigt område, og
    får først derefter deres endelige 1..N-værdi."""
    items: list[tuple[datetime | None, str, object]] = []
    for collection_name in (MOVIE_COLLECTION, TV_SHOW_COLLECTION):
        cursor = db[collection_name].find(
            {
                "media_type": DIGITAL,
                "serial_number": {"$exists": True, "$lt": OTHER_SERIAL_START},
            },
            {"_id": 1, "created_at": 1},
        )
        async for doc in cursor:
            items.append((doc.get("created_at"), collection_name, doc["_id"]))

    items.sort(key=lambda item: item[0] or datetime.min)

    for index, (_, collection_name, doc_id) in enumerate(items, start=1):
        await set_serial(db, collection_name, doc_id, _RENUMBER_TEMP_OFFSET + index)

    for index, (_, collection_name, doc_id) in enumerate(items, start=1):
        await set_serial(db, collection_name, doc_id, index)

    next_value = len(items) + 1
    await db[COUNTERS_COLLECTION].update_one(
        {"_id": SERIAL_COUNTER_ID}, {"$set": {"next_value": next_value}}, upsert=True
    )

    if items:
        logger.info("D#-serie omnummereret fra 1: %s digitale poster (feature #188)", len(items))
    return len(items)
