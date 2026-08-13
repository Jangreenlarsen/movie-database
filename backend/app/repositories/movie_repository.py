import logging
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.movie import MediaType, subtitles_from_free_text
from app.repositories import digital_serial_repository
from app.repositories.text_search import build_text_query, drop_legacy_text_index

COLLECTION = "movies"
DELETED_COLLECTION = "deleted_movies"
COUNTERS_COLLECTION = "counters"
SERIAL_COUNTER_ID = "movie_serial"
DEFAULT_SERIAL_CONFIG = {"next_value": 1, "increment": 1, "padding_width": 0}
MAX_SERIAL_ASSIGN_ATTEMPTS = 10_000
# Den digitale serie tælles for sig (digital_serial_repository).
DIGITAL_MEDIA_TYPE = "Digital"

# Feature #96 — serie-bogstav -> medietype, så en søgning på "M42" kan
# afgrænses til den fysiske serie og "D42" til den digitale. Bogstaverne
# spejler præfikserne i frontendens `utils/serialNumber.js`.
SERIAL_PREFIXES = {"M": "Fysisk", "D": "Digital"}

logger = logging.getLogger("moviedb")

# Whitelist mapping API-facing sort keys -> actual document fields, so an
# arbitrary/unindexed field can never be requested via the query string.
# Feature #96 — et sorterings-valg kan nu udvide til flere mongo-nøgler.
# Hver post er en liste af (felt, tilstand): "user" følger brugerens
# op/ned-knap, mens "asc"/"desc" er låst. Serienumrene sorteres sammensat,
# fordi de tre serier (M/T/D) tælles hver for sig — uden serie-nøglen ville
# M1 og D1 blande sig med hinanden i listen. Serie-nøglen er låst, så
# op/ned-knappen kun vender selve nummer-rækkefølgen og ikke også flytter
# den ene serie hen over den anden.
#
# "Digital" < "Fysisk" alfabetisk, så media_type stigende giver D først.
# Det er en egenskab ved etiketterne, ikke et tilfælde vi må glemme —
# test_serial_series_sort_order_depends_on_label_ordering låser den fast.
SORT_FIELDS = {
    "title": [("title", "user")],
    "year": [("year", "user")],
    # Standard-valget: alle D-numre først, derefter de fysiske (Jans krav
    # 2026-08-08).
    "serial_number": [("media_type", "asc"), ("serial_number", "user")],
    # Samme liste, men med den fysiske serie først.
    "serial_number_physical": [("media_type", "desc"), ("serial_number", "user")],
    "created_at": [("created_at", "user")],
    "rating": [("rating", "user")],
    "personal_rating": [("personal_rating", "user")],
    "runtime": [("runtime", "user")],
    "format": [("format", "user")],
    "audio_types": [("audio_types", "user")],
    "media_type": [("media_type", "user")],
    "location": [("location", "user")],
    "owner": [("owner", "user")],
    "registered_by": [("registered_by", "user")],
    "watched_at": [("watched_at", "user")],
    # Feature #127 — bestillingsstatus (kun sat på ønskeliste-poster, feature
    # #114; None = ikke bestilt, sorteres først stigende). Meningsfuldt på
    # ønskelisten; på det ejede bibliotek er feltet altid None (no-op).
    "order_status": [("order_status", "user")],
}
DEFAULT_SORT_FIELD = "created_at"
MAX_SORT_LEVELS = 3

# Felterne fritekst-søgningen (`?q=`) rammer. Skuespiller/instruktør/genre er
# med her, fordi både søgefeltets placeholder og CLAUDE.md regel 7 lover dem —
# det gjorde det gamle `$text`-index ikke (BUGS.md #48).
TEXT_SEARCH_FIELDS = ["title", "overview", "cast", "director", "genres"]

# AudioType label-historik -> de nuværende værdier — se
# `_migrate_audio_type_labels` og `models/movie.py::AudioType`.
#
# OBS: audio-migrationen laver ét dict-opslag pr. label (ikke en sekventiel
# kaskade som format-migrationen), så hvert *mellemliggende* label skal pege
# DIREKTE på slutværdien. Derfor mapper både "DTS-HD Master Audio" (pre-v0.22.0)
# og "DTS-HD-M" (v0.22.0-v0.104.x) til den nye "DTS-HD5.1" (v0.105.0).
_AUDIO_TYPE_LABEL_MIGRATIONS = {
    "Dolby Digital": "DD",
    "Dolby Digital 5.1": "DD5.1",
    "Dolby Digital 7.1": "DD7.1",
    "DTS-HD Master Audio": "DTS-HD5.1",
    "DTS-HD-M": "DTS-HD5.1",
    "DTS-HD-MA-7.1": "DTS-HD7.1",
    "Dolby Atmos": "Atmos",
    "Dolby TrueHD": "D-true-HD",
}


async def _migrate_audio_type_labels(db: AsyncIOMotorDatabase) -> None:
    """One-time rewrite of existing documents' `audio_types` values from the
    old, longer labels to the new short ones, so they keep validating
    against `AudioType` on the next edit and keep matching the (now
    relabeled) filter chips. Done document-by-document in Python rather than
    a single `arrayFilters` update, since mongomock's support for it is
    inconsistent (see BUGS.md #1's note on mongomock's sparse-index gaps —
    same category of testsuite-vs-real-Mongo mismatch)."""
    collection = db[COLLECTION]
    cursor = collection.find(
        {"audio_types": {"$in": list(_AUDIO_TYPE_LABEL_MIGRATIONS)}}, {"audio_types": 1}
    )
    async for doc in cursor:
        relabeled = [
            _AUDIO_TYPE_LABEL_MIGRATIONS.get(label, label) for label in doc.get("audio_types", [])
        ]
        if relabeled != doc.get("audio_types", []):
            await collection.update_one({"_id": doc["_id"]}, {"$set": {"audio_types": relabeled}})


# Pre-v0.22.0 MovieFormat labels -> the new, shorter ones. "Digital" had no
# quality tier before this version, so it can't be migrated exactly — it
# defaults to "Digital-HD" (the most common digital-purchase quality); check
# BUGS.md/CHANGELOG.md and correct any that should be UHD/STD instead.
#
# v0.84.0 — the digital tiers themselves got the same short-label treatment
# ("Digital-HD" -> "D-HD" etc.), and v0.105.0 renamed those to resolution-based
# labels ("D-HD" -> "D-1080", "D-UHD" -> "D-4K") — Jans ønske 2026-08-12.
# These entries run in dict-insertion order (Python 3.7+), and the format
# migration applies them as sequential `update_many`s, so the whole history
# cascades in one call: "Digital" -> "Digital-HD" -> "D-HD" -> "D-1080".
_FORMAT_LABEL_MIGRATIONS = {
    "Blu-ray": "BD",
    "4K Ultra HD": "UHD",
    "Digital": "Digital-HD",
    "Digital-UHD": "D-UHD",
    "Digital-HD": "D-HD",
    "Digital-STD": "D-SD",
    "D-UHD": "D-4K",
    "D-HD": "D-1080",
    # v0.108.0 — fysiske formater fik "F-"-præfiks, D-SD -> D-480, og VHS
    # fjernet (migreres til F-DVD, Jans valg 2026-08-12). Kaskaden ovenfra
    # fortsætter: Blu-ray -> BD -> F-BD, 4K Ultra HD -> UHD -> F-UHD,
    # Digital-STD -> D-SD -> D-480.
    "D-SD": "D-480",
    "DVD": "F-DVD",
    "BD": "F-BD",
    "UHD": "F-UHD",
    "VHS": "F-DVD",
}


async def _migrate_format_labels(db: AsyncIOMotorDatabase) -> None:
    """One-time rewrite of existing documents' `format` value from the old,
    longer labels to the new short ones — same rationale as
    `_migrate_audio_type_labels`, but `format` is a single field, not an
    array, so a plain `update_many` per old value suffices."""
    collection = db[COLLECTION]
    for old_label, new_label in _FORMAT_LABEL_MIGRATIONS.items():
        await collection.update_many({"format": old_label}, {"$set": {"format": new_label}})


async def _migrate_subtitles_to_list(db: AsyncIOMotorDatabase) -> None:
    """Feature #123 — undertekster gik fra en fri enkelt-streng til en liste
    (afkryds Eng/DK + fritekst under "Andet"). Konvertér eksisterende
    streng-værdier til liste-form, så de fortsat validerer mod modellen og
    vises korrekt i det nye UI. Dokument-for-dokument i Python (samme
    begrundelse som `_migrate_audio_type_labels`): en streng skal parses,
    hvilket `update_many` ikke kan. En allerede-migreret liste røres ikke."""
    collection = db[COLLECTION]
    cursor = collection.find({"subtitles": {"$exists": True}}, {"subtitles": 1})
    async for doc in cursor:
        value = doc.get("subtitles")
        if isinstance(value, str):
            await collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"subtitles": subtitles_from_free_text(value)}},
            )


async def _migrate_watched_at_to_date(db: AsyncIOMotorDatabase) -> None:
    """BUGS.md #59 — `update_movie` gemte tidligere `watched_at` som en ISO-
    streng (`model_dump(mode="json")`), ikke som en Date. Konverter eksisterende
    streng-værdier, så feltets BSON-type er konsistent med `created_at`/
    `updated_at` og dato-interval-forespørgsler virker (samme klasse som
    BUGS.md #33). Idempotent: rører kun dokumenter hvor feltet er en streng."""
    collection = db[COLLECTION]
    cursor = collection.find({"watched_at": {"$exists": True, "$ne": None}}, {"watched_at": 1})
    async for doc in cursor:
        value = doc.get("watched_at")
        if not isinstance(value, str):
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:  # pragma: no cover - ubrugelig streng, lades urørt
            continue
        await collection.update_one({"_id": doc["_id"]}, {"$set": {"watched_at": parsed}})


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    collection = db[COLLECTION]
    await _migrate_audio_type_labels(db)
    await _migrate_format_labels(db)
    await _migrate_subtitles_to_list(db)
    await _migrate_watched_at_to_date(db)
    # BUGS.md #48 — søgningen går ikke længere gennem `$text`; det gamle
    # text-index ryddes op så det ikke koster skrivetid uden at blive brugt.
    await drop_legacy_text_index(collection)
    await collection.create_index("tags_normalized")
    await collection.create_index("barcode", unique=True, sparse=True)
    await collection.create_index("format")
    await collection.create_index("audio_types")
    await collection.create_index("media_type")

    # Migrate the pre-v0.18.0 serial_number index (unique, NOT sparse) to
    # sparse — wishlist movies (FEATURES.md #28) omit serial_number entirely,
    # and a non-sparse unique index would treat every such document as a
    # colliding `null`. Mongo refuses to silently redefine an existing index
    # under the same auto-generated name with different options, so an
    # old non-sparse index must be dropped before the sparse one is created.
    # Feature #93 — det unikke index er nu sammensat af nummer *og* medietype.
    # Den fysiske og den digitale serie tælles hver for sig, så M#5 og D#5 er
    # to forskellige udgaver og skal kunne findes side om side; et unikt index
    # på nummeret alene ville afvise den anden. `partialFilterExpression`
    # frem for `sparse`: et sammensat sparse-index indekserer et dokument så
    # snart *ét* af felterne findes, hvilket ville få to nummerløse poster med
    # samme medietype til at kollidere på (null, "Fysisk").
    existing_indexes = await collection.index_information()
    for legacy_name in ("serial_number_1",):
        if legacy_name in existing_indexes:
            await collection.drop_index(legacy_name)
    await collection.create_index(
        [("serial_number", 1), ("media_type", 1)],
        unique=True,
        partialFilterExpression={"serial_number": {"$exists": True}},
        name="serial_number_media_type",
    )
    # Krydset mellem de to collections kan et index ikke håndhæve — se
    # digital_serial_repository.next_serial_number.
    await digital_serial_repository.backfill(db, COLLECTION)

    await collection.create_index("is_wishlist")
    await collection.create_index("rating")
    await collection.create_index("personal_rating")
    await collection.create_index("watched")
    await collection.create_index("watched_at")
    await collection.create_index("cast")
    await collection.create_index("director")
    await collection.create_index("collection_id")
    await collection.create_index("year")
    await collection.create_index("created_at")
    await collection.create_index("runtime")
    await collection.create_index("location")
    await collection.create_index("owner")
    await collection.create_index("registered_by")
    await collection.create_index("order_status")  # feature #127 — sorterbart felt
    await db[DELETED_COLLECTION].create_index("deleted_at")


async def _ensure_serial_config(db: AsyncIOMotorDatabase) -> dict:
    doc = await db[COUNTERS_COLLECTION].find_one({"_id": SERIAL_COUNTER_ID})
    if doc is None:
        doc = {"_id": SERIAL_COUNTER_ID, **DEFAULT_SERIAL_CONFIG}
        await db[COUNTERS_COLLECTION].insert_one(doc)
        return doc

    if "next_value" not in doc:
        # Migrate the pre-v0.9.0 counter shape ({"value": <last assigned>})
        # to the configurable one ({"next_value": <to assign next>, ...}).
        next_value = doc.get("value", 0) + 1
        await db[COUNTERS_COLLECTION].update_one(
            {"_id": SERIAL_COUNTER_ID},
            {"$set": {"next_value": next_value}, "$unset": {"value": ""}},
        )
        doc = await db[COUNTERS_COLLECTION].find_one({"_id": SERIAL_COUNTER_ID})

    return doc


async def get_serial_config(db: AsyncIOMotorDatabase) -> dict:
    config = await _ensure_serial_config(db)
    return {
        "start_number": config.get("next_value", DEFAULT_SERIAL_CONFIG["next_value"]),
        "increment": config.get("increment", DEFAULT_SERIAL_CONFIG["increment"]),
        "padding_width": config.get("padding_width", DEFAULT_SERIAL_CONFIG["padding_width"]),
        # Feature #131 — det fælles genbrugs-flag (bor i digital_serial_repository,
        # så alle tre serier læser samme kilde).
        "reuse_freed": await digital_serial_repository.is_reuse_enabled(db),
    }


async def update_serial_config(db: AsyncIOMotorDatabase, updates: dict) -> dict:
    """`start_number` is a one-off "assign this to the next movie" action, not
    a historical origin — it directly moves the next-value pointer.
    `increment` only changes the step size going forward. `padding_width`
    is display-only. `reuse_freed` (feature #131) er den fælles genbrugs-til/fra."""
    await _ensure_serial_config(db)

    mongo_updates: dict = {}
    if "start_number" in updates:
        mongo_updates["next_value"] = updates["start_number"]
    if "increment" in updates:
        mongo_updates["increment"] = updates["increment"]
    if "padding_width" in updates:
        mongo_updates["padding_width"] = updates["padding_width"]

    if mongo_updates:
        await db[COUNTERS_COLLECTION].update_one(
            {"_id": SERIAL_COUNTER_ID}, {"$set": mongo_updates}
        )
    if "reuse_freed" in updates:
        await digital_serial_repository.set_reuse_enabled(db, updates["reuse_freed"])
    return await get_serial_config(db)


async def free_serial_numbers(db: AsyncIOMotorDatabase) -> list[int]:
    """Feature #131 — de frigjorte M#-numre (huller i det brugte interval),
    laveste først. Den fysiske film-serie: poster med medietype != Digital
    (uklassificerede tælles med som fysiske, jf. next_serial_number)."""
    taken: set[int] = set()
    # Feature #139 — 5000+-pulje-numre hører ikke til M#-serien; udelades her, så
    # M#-genbruget og "Ledige numre"-oversigten ikke rækker op til 5000+.
    cursor = db[COLLECTION].find(
        {
            "serial_number": {"$exists": True, "$lt": digital_serial_repository.OTHER_SERIAL_START},
            "media_type": {"$ne": DIGITAL_MEDIA_TYPE},
        },
        {"serial_number": 1},
    )
    async for doc in cursor:
        number = doc.get("serial_number")
        if isinstance(number, int):
            taken.add(number)
    return digital_serial_repository.gaps(taken)


async def _next_from_counter(db: AsyncIOMotorDatabase) -> int:
    """Race-safe even under concurrent creates. If the next value is already
    taken (possible right after `start_number` was moved onto an
    already-assigned number), keeps advancing by `increment` until a free
    one is found."""
    for _ in range(MAX_SERIAL_ASSIGN_ATTEMPTS):
        config = await _ensure_serial_config(db)
        increment = config.get("increment", DEFAULT_SERIAL_CONFIG["increment"])

        before = await db[COUNTERS_COLLECTION].find_one_and_update(
            {"_id": SERIAL_COUNTER_ID},
            {"$inc": {"next_value": increment}},
            return_document=ReturnDocument.BEFORE,
        )
        candidate = before["next_value"]

        # Feature #93 — kun den fysiske serie tælles her. Uden filteret på
        # medietype ville en digital post med samme nummer få tælleren til at
        # springe videre, og de to serier ville dermed påvirke hinanden
        # selvom de er uafhængige. Poster helt uden medietype tælles med som
        # fysiske: de er fra før reglen, og deres nummer kan stå skrevet på
        # et cover.
        taken = await db[COLLECTION].find_one(
            {"serial_number": candidate, "media_type": {"$ne": DIGITAL_MEDIA_TYPE}}, {"_id": 1}
        )
        if taken is None:
            return candidate

    raise RuntimeError("Could not find a free serial number after many attempts")


async def next_serial_number(db: AsyncIOMotorDatabase) -> int:
    """Feature #131 — genbruger det laveste frigjorte M#-nummer hvis genbrug er
    slået til og der findes et hul; ellers fra tælleren som hidtil."""
    if await digital_serial_repository.is_reuse_enabled(db):
        free = await free_serial_numbers(db)
        if free:
            return free[0]
    return await _next_from_counter(db)



async def count_library_by_media_type(db: AsyncIOMotorDatabase) -> dict:
    """Feature #94 — antal biblioteksposter (ønsker ekskluderet), delt op på
    medietype. Tre `count_documents` frem for at hente dokumenterne: hele
    optaellingen skal kunne staa i app-hovedet paa hver eneste sideindlaesning,
    saa den maa ikke koste mere end et par index-opslag."""
    library = {"is_wishlist": {"$ne": True}}
    total = await db[COLLECTION].count_documents(library)
    physical = await db[COLLECTION].count_documents({**library, "media_type": "Fysisk"})
    digital = await db[COLLECTION].count_documents({**library, "media_type": DIGITAL_MEDIA_TYPE})
    wishlist = await db[COLLECTION].count_documents({"is_wishlist": True})
    return {
        "total": total,
        "physical": physical,
        "digital": digital,
        # Poster fra foer medietype blev paakraevet (feature #92).
        "unclassified": total - physical - digital,
        "wishlist": wishlist,
    }

async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_id(db: AsyncIOMotorDatabase, movie_id: str) -> dict | None:
    if not ObjectId.is_valid(movie_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(movie_id)})


async def find_by_tmdb_id(db: AsyncIOMotorDatabase, tmdb_id: int) -> list[dict]:
    """All existing documents (library and/or wishlist) for a given TMDb id —
    used for the pre-save duplicate warning (FEATURES.md #38). More than one
    match is possible and legitimate (e.g. two physical copies)."""
    cursor = db[COLLECTION].find({"tmdb_id": tmdb_id})
    return await cursor.to_list(length=100)


async def find_all_library_movies(db: AsyncIOMotorDatabase) -> list[dict]:
    """All non-wishlist movies, uncapped by the normal 500-item page size —
    used for the statistics page (FEATURES.md #43), which must cover the
    whole collection, not just a page of it. Same "$ne: True" pattern as
    find_many's default is_wishlist filter."""
    cursor = db[COLLECTION].find({"is_wishlist": {"$ne": True}})
    return await cursor.to_list(length=10_000)


async def find_by_tmdb_ids(db: AsyncIOMotorDatabase, tmdb_ids: list[int]) -> list[dict]:
    """Batch lookup for feature #42 (collection ownership) — a single query
    instead of one per collection part."""
    if not tmdb_ids:
        return []
    cursor = db[COLLECTION].find({"tmdb_id": {"$in": tmdb_ids}})
    return await cursor.to_list(length=len(tmdb_ids))


async def find_all_with_tmdb_id(db: AsyncIOMotorDatabase) -> list[dict]:
    """Movies whose metadata was originally sourced from TMDb — the only
    ones a bulk re-sync (FEATURES.md #33) can refresh anything for."""
    cursor = db[COLLECTION].find({"tmdb_id": {"$ne": None}})
    return await cursor.to_list(length=10_000)


async def find_all_raw(db: AsyncIOMotorDatabase) -> list[dict]:
    """Every movie document, unbounded — unlike `find_many`'s 500-document
    page cap, this backs the full-library export (feature #60)."""
    return await db[COLLECTION].find({}).to_list(length=None)


async def find_all_for_plex_match(db: AsyncIOMotorDatabase) -> list[dict]:
    """Kun de fire felter Plex-matchning bruger (feature #88). En projektion
    frem for `find_all_raw`, fordi dette kald rammer hver gang biblioteket
    vises — at trække poster-URL'er, cast-lister og noter med ville være
    mange gange så meget data for et opslag der kun ser på id, titel og år.

    Ønskelisten er bevidst med: at en ønsket film allerede ligger i Plex er
    netop den slags man vil kunne se på kortet.

    En *fysisk* post er derimod bevidst UDE (Jans ønske 2026-08-10): en
    fysisk DVD man også har liggende digitalt i Plex skal kunne stå som to
    separate poster i biblioteket — den fysiske skal aldrig få et "ligger i
    Plex"-badge (den ligger jo netop på hylden, ikke i Plex), og skal aldrig
    forhindre selve den digitale udgave i at blive importeret ved at blive
    talt som "har den allerede" (se `plex_service.import_from_plex`'s brug
    af denne funktion til dublet-tjek). `$ne` frem for et eksplicit
    `"Digital"`-filter, så en ønske-post (intet medietype endnu) og en
    endnu ikke klassificeret post fortsat er med, jf. CLAUDE.md regel 16
    ("regler der kun gælder én gren")."""
    cursor = db[COLLECTION].find(
        {"media_type": {"$ne": MediaType.PHYSICAL.value}},
        {"_id": 1, "tmdb_id": 1, "title": 1, "year": 1},
    )
    return await cursor.to_list(length=None)


async def replace_all(db: AsyncIOMotorDatabase, documents: list[dict]) -> None:
    """Wholesale replace of the collection — used only by the library
    import/restore (feature #60). Not wrapped in a transaction (this app
    runs against a standalone MongoDB, not a replica set) — a failure
    partway through an `insert_many` can leave the collection with only
    some of the imported documents; the caller surfaces that as an error
    rather than silently reporting success."""
    await db[COLLECTION].delete_many({})
    if documents:
        await db[COLLECTION].insert_many(documents)


async def bump_serial_counter_past(db: AsyncIOMotorDatabase, documents: list[dict]) -> None:
    """After a wholesale import, the next auto-assigned serial number must
    be higher than any serial number the import just brought in — otherwise
    the very next created movie could collide with an imported one."""
    existing_serials = [doc["serial_number"] for doc in documents if doc.get("serial_number") is not None]
    if not existing_serials:
        return
    config = await _ensure_serial_config(db)
    if config.get("next_value", 0) <= max(existing_serials):
        await db[COUNTERS_COLLECTION].update_one(
            {"_id": SERIAL_COUNTER_ID}, {"$set": {"next_value": max(existing_serials) + 1}}
        )


async def distinct_owners(db: AsyncIOMotorDatabase) -> list[str]:
    """Owner values already in use across the collection — feeds the
    owner-field combobox (FEATURES.md #58) alongside `tv_show_repository`'s
    counterpart."""
    values = await db[COLLECTION].distinct("owner")
    return [v for v in values if v]


async def distinct_locations(db: AsyncIOMotorDatabase) -> list[str]:
    """Same as `distinct_owners`, for the location field."""
    values = await db[COLLECTION].distinct("location")
    return [v for v in values if v]


async def distinct_genres(db: AsyncIOMotorDatabase) -> list[str]:
    """Feature #111 — genre-værdier der rent faktisk findes i biblioteket, til
    filter-panelets afkrydsning. `.distinct()` på et array-felt unwinder det
    automatisk til de enkelte værdier — samme mekanisme som
    `distinct_owners`/`distinct_locations`, bare på et array-felt i stedet
    for et skalar-felt. Bevidst IKKE slået sammen med TV-seriernes genrer
    (modsat owner/location i attribute_service): TMDb's film- og
    serie-genrer er to forskellige lister med delvist overlap, og hver fane
    filtrerer alligevel kun sin egen ressource."""
    values = await db[COLLECTION].distinct("genres")
    return sorted({v for v in values if v}, key=str.casefold)


async def set_serial_number(db: AsyncIOMotorDatabase, movie_id: str, serial_number: int) -> None:
    await db[COLLECTION].update_one(
        {"_id": ObjectId(movie_id)}, {"$set": {"serial_number": serial_number}}
    )


async def clear_serial_number(db: AsyncIOMotorDatabase, movie_id: str) -> None:
    """Removes the field entirely (not `$set` to null) — same "omit, don't
    null" pattern as `barcode` (BUGS.md #1/#10), required for the sparse
    unique index on `serial_number` to treat this movie as unnumbered."""
    await db[COLLECTION].update_one(
        {"_id": ObjectId(movie_id)}, {"$unset": {"serial_number": ""}}
    )


def _build_find_many_filter(
    query: str | None,
    normalized_tags: list[str] | None,
    formats: list[str] | None = None,
    audio_types: list[str] | None = None,
    media_types: list[str] | None = None,
    is_wishlist: bool = False,
    watched: bool | None = None,
    cast: str | None = None,
    director: str | None = None,
    genres: list[str] | None = None,
) -> dict:
    """`is_wishlist=False` matches both `is_wishlist: false` *and* documents
    that predate this field entirely (`$ne: True`, not a `False` equality
    check) — see FEATURES.md #28 and BUGS.md's "check every representation
    of empty" lesson (CLAUDE.md regel 16). Shared by `find_many`/`count_many`
    (feature #15) so the two can never drift apart on what counts as a
    match."""
    filter_: dict = {"is_wishlist": True if is_wishlist else {"$ne": True}}
    if query:
        text_query = build_text_query(query, TEXT_SEARCH_FIELDS, SERIAL_PREFIXES)
        if text_query:
            filter_.update(text_query)
    if normalized_tags:
        filter_["tags_normalized"] = {"$all": normalized_tags}
    if formats:
        filter_["format"] = {"$in": formats}
    if audio_types:
        filter_["audio_types"] = {"$in": audio_types}
    if media_types:
        filter_["media_type"] = {"$in": media_types}
    if genres:
        # $in, ikke $all — samme "vis alt der matcher mindst én valgt chip"
        # semantik som format/audio_types/media_types ovenfor, ikke
        # tags_normalized's "skal have dem alle".
        filter_["genres"] = {"$in": genres}
    if watched is not None:
        # Same "missing field != False" pitfall as is_wishlist above — movies
        # created before this feature (or simply never marked) have no
        # `watched` key at all, so `False` must match "not True", not a
        # literal equality check that would silently exclude them.
        filter_["watched"] = True if watched else {"$ne": True}
    if cast:
        filter_["cast"] = cast
    if director:
        filter_["director"] = director
    return filter_


async def find_many(
    db: AsyncIOMotorDatabase,
    query: str | None,
    normalized_tags: list[str] | None,
    formats: list[str] | None = None,
    audio_types: list[str] | None = None,
    media_types: list[str] | None = None,
    sort_spec: list[tuple[str, int]] | None = None,
    is_wishlist: bool = False,
    watched: bool | None = None,
    cast: str | None = None,
    director: str | None = None,
    skip: int = 0,
    limit: int | None = None,
    genres: list[str] | None = None,
) -> list[dict]:
    """`sort_spec` is a list of up to `MAX_SORT_LEVELS` (already-whitelisted
    mongo field name, direction) tuples for compound multi-level sorting
    (see FEATURES.md #17/#27) — validation against `SORT_FIELDS` happens in
    `movie_service`, this layer just applies whatever it is given.

    `limit=None` (the default) fetches every match, no cap — used by callers
    that need the whole filtered set (Print-siden, Voldby BIO's søgning).
    `movie_service.list_movies` passes a real `limit` for the paginated
    library view (feature #15), which used to be silently capped at 500
    with no way to see or reach anything past it."""
    filter_ = _build_find_many_filter(
        query, normalized_tags, formats, audio_types, media_types, is_wishlist, watched, cast, director, genres
    )
    cursor = db[COLLECTION].find(filter_)
    cursor = cursor.sort(sort_spec) if sort_spec else cursor.sort(DEFAULT_SORT_FIELD, -1)
    if skip:
        cursor = cursor.skip(skip)
    if limit is not None:
        cursor = cursor.limit(limit)
    return await cursor.to_list(length=limit)


async def count_many(
    db: AsyncIOMotorDatabase,
    query: str | None,
    normalized_tags: list[str] | None,
    formats: list[str] | None = None,
    audio_types: list[str] | None = None,
    media_types: list[str] | None = None,
    is_wishlist: bool = False,
    watched: bool | None = None,
    cast: str | None = None,
    director: str | None = None,
    genres: list[str] | None = None,
) -> int:
    filter_ = _build_find_many_filter(
        query, normalized_tags, formats, audio_types, media_types, is_wishlist, watched, cast, director, genres
    )
    return await db[COLLECTION].count_documents(filter_)


async def update(db: AsyncIOMotorDatabase, movie_id: str, fields: dict) -> dict | None:
    if not ObjectId.is_valid(movie_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(movie_id)}, {"$set": fields})
    return await db[COLLECTION].find_one({"_id": ObjectId(movie_id)})


async def delete(db: AsyncIOMotorDatabase, movie_id: str) -> bool:
    if not ObjectId.is_valid(movie_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(movie_id)})
    return result.deleted_count > 0


async def archive_deleted(db: AsyncIOMotorDatabase, movie_doc: dict, deleted_by: str) -> None:
    """Logs a deleted movie (serial_number, title, when, who) before the
    document itself is removed from `movies` — see FEATURES.md #29. Once the
    document is gone, its serial_number is no longer taken, so it is
    automatically free for the counter or a manual edit to reuse."""
    await db[DELETED_COLLECTION].insert_one(
        {
            "movie_id": movie_doc["_id"],
            "serial_number": movie_doc.get("serial_number"),
            "title": movie_doc["title"],
            "year": movie_doc.get("year"),
            "format": movie_doc.get("format"),
            "deleted_at": datetime.now(timezone.utc),
            "deleted_by": deleted_by,
        }
    )


async def list_deleted(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db[DELETED_COLLECTION].find().sort("deleted_at", -1)
    return await cursor.to_list(length=1000)
