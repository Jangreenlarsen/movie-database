import logging
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.movie import MediaType, subtitles_from_free_text
from app.repositories import digital_serial_repository
from app.repositories.text_search import build_text_query, drop_legacy_text_index

COLLECTION = "tv_shows"
DELETED_COLLECTION = "deleted_tv_shows"
COUNTERS_COLLECTION = "counters"
# Separate counter from movies' "movie_serial" — TV shows are a fully
# separate resource (Jan's explicit choice, 2026-08-02), so a separate
# physical numbering sequence is the more conservative default. Easy to
# unify later if that turns out to be wrong.
SERIAL_COUNTER_ID = "tv_show_serial"
DEFAULT_SERIAL_CONFIG = {"next_value": 1, "increment": 1, "padding_width": 0}
MAX_SERIAL_ASSIGN_ATTEMPTS = 10_000
# Den digitale serie tælles for sig (digital_serial_repository).
DIGITAL_MEDIA_TYPE = "Digital"

# Feature #96 — se movie_repository.SERIAL_PREFIXES. TV-serier bruger T for
# den fysiske serie; den digitale deles med filmene.
SERIAL_PREFIXES = {"T": "Fysisk", "D": "Digital"}

logger = logging.getLogger("moviedb")

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
    "name": [("name", "user")],
    "year": [("year", "user")],
    # Standard-valget: alle D-numre først, derefter de fysiske (Jans krav
    # 2026-08-08).
    "serial_number": [("media_type", "asc"), ("serial_number", "user")],
    # Samme liste, men med den fysiske serie først.
    "serial_number_physical": [("media_type", "desc"), ("serial_number", "user")],
    "created_at": [("created_at", "user")],
    "rating": [("rating", "user")],
    "personal_rating": [("personal_rating", "user")],
    "format": [("format", "user")],
    "audio_types": [("audio_types", "user")],
    "media_type": [("media_type", "user")],
    "location": [("location", "user")],
    "owner": [("owner", "user")],
    "registered_by": [("registered_by", "user")],
    "watched_at": [("watched_at", "user")],
    # Feature #127 — se den identiske note i movie_repository.
    "order_status": [("order_status", "user")],
}
DEFAULT_SORT_FIELD = "created_at"
MAX_SORT_LEVELS = 3

# Spejler movie_repository.TEXT_SEARCH_FIELDS — TV-serier har `creators`
# hvor film har `director` (BUGS.md #48).
TEXT_SEARCH_FIELDS = ["name", "overview", "cast", "creators", "genres"]

# v0.84.0 — samme relabel som movie_repository._FORMAT_LABEL_MIGRATIONS, men
# kun de digitale niveauer: TV-serier fandtes ikke endnu ved den første
# format-omdøbning (v0.22.0), så Blu-ray/4K Ultra HD er der intet at
# migrere. Plex-importen (feature #91) skriver derimod digitale
# kvalitetsniveauer på TV-serier lige så vel som på film.
_FORMAT_LABEL_MIGRATIONS = {
    "Digital-UHD": "D-UHD",
    "Digital-HD": "D-HD",
    "Digital-STD": "D-SD",
}


async def _migrate_format_labels(db: AsyncIOMotorDatabase) -> None:
    """Se den identiske funktion i movie_repository.py."""
    collection = db[COLLECTION]
    for old_label, new_label in _FORMAT_LABEL_MIGRATIONS.items():
        await collection.update_many({"format": old_label}, {"$set": {"format": new_label}})


async def _migrate_subtitles_to_list(db: AsyncIOMotorDatabase) -> None:
    """Feature #123 — se den identiske funktion i movie_repository.py. TV-serier
    fik også det frie undertekst-felt (#109), så deres streng-værdier skal
    konverteres til liste-form på samme måde."""
    collection = db[COLLECTION]
    cursor = collection.find({"subtitles": {"$exists": True}}, {"subtitles": 1})
    async for doc in cursor:
        value = doc.get("subtitles")
        if isinstance(value, str):
            await collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"subtitles": subtitles_from_free_text(value)}},
            )


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    collection = db[COLLECTION]
    await _migrate_format_labels(db)
    await _migrate_subtitles_to_list(db)
    # BUGS.md #48 — se movie_repository: søgningen bruger ikke længere
    # `$text`, så det gamle index ryddes op i stedet for at ligge og koste
    # skrivetid.
    await drop_legacy_text_index(collection)
    await collection.create_index("tags_normalized")
    await collection.create_index("barcode", unique=True, sparse=True)
    await collection.create_index("format")
    await collection.create_index("audio_types")
    await collection.create_index("media_type")
    # Feature #93 — se den identiske note i movie_repository: unikt pr.
    # (nummer, medietype), så T#5 og D#5 kan findes side om side.
    existing_indexes = await collection.index_information()
    if "serial_number_1" in existing_indexes:
        await collection.drop_index("serial_number_1")
    await collection.create_index(
        [("serial_number", 1), ("media_type", 1)],
        unique=True,
        partialFilterExpression={"serial_number": {"$exists": True}},
        name="serial_number_media_type",
    )
    await digital_serial_repository.backfill(db, COLLECTION)
    await collection.create_index("is_wishlist")
    await collection.create_index("rating")
    await collection.create_index("personal_rating")
    await collection.create_index("watched")
    await collection.create_index("watched_at")
    await collection.create_index("year")
    await collection.create_index("created_at")
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


async def next_serial_number(db: AsyncIOMotorDatabase) -> int:
    """Same race-safe skip-collisions approach as movie_repository's
    version — see there for the full rationale."""
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


async def find_by_id(db: AsyncIOMotorDatabase, tv_show_id: str) -> dict | None:
    if not ObjectId.is_valid(tv_show_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(tv_show_id)})


async def find_by_tmdb_id(db: AsyncIOMotorDatabase, tmdb_id: int) -> list[dict]:
    cursor = db[COLLECTION].find({"tmdb_id": tmdb_id})
    return await cursor.to_list(length=100)


async def find_all_with_tmdb_id(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db[COLLECTION].find({"tmdb_id": {"$ne": None}})
    return await cursor.to_list(length=10_000)


async def find_all_raw(db: AsyncIOMotorDatabase) -> list[dict]:
    """Every TV show document, unbounded — backs the full-library export
    (feature #60), unlike `find_many`'s 500-document page cap."""
    return await db[COLLECTION].find({}).to_list(length=None)


async def find_all_for_plex_match(db: AsyncIOMotorDatabase) -> list[dict]:
    """TV-siden af feature #88 — spejler movie_repository.find_all_for_plex_match
    (inkl. 2026-08-10-udelukkelsen af fysiske poster), bortset fra
    titel-feltet, som her hedder `name`."""
    cursor = db[COLLECTION].find(
        {"media_type": {"$ne": MediaType.PHYSICAL.value}},
        {"_id": 1, "tmdb_id": 1, "name": 1, "year": 1},
    )
    return await cursor.to_list(length=None)


async def find_all_library_tv_shows(db: AsyncIOMotorDatabase) -> list[dict]:
    """All non-wishlist TV shows, uncapped — mirrors
    movie_repository.find_all_library_movies, used by the Statistik-side's
    stregkode-kilde-breakdown (feature #77), which covers film+TV."""
    cursor = db[COLLECTION].find({"is_wishlist": {"$ne": True}})
    return await cursor.to_list(length=None)


async def replace_all(db: AsyncIOMotorDatabase, documents: list[dict]) -> None:
    """Wholesale replace of the collection — see movie_repository's
    counterpart for the same not-a-transaction caveat."""
    await db[COLLECTION].delete_many({})
    if documents:
        await db[COLLECTION].insert_many(documents)


async def bump_serial_counter_past(db: AsyncIOMotorDatabase, documents: list[dict]) -> None:
    """See movie_repository's counterpart — same rationale."""
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
    owner-field combobox (FEATURES.md #58) alongside `movie_repository`'s
    counterpart."""
    values = await db[COLLECTION].distinct("owner")
    return [v for v in values if v]


async def distinct_locations(db: AsyncIOMotorDatabase) -> list[str]:
    """Same as `distinct_owners`, for the location field."""
    values = await db[COLLECTION].distinct("location")
    return [v for v in values if v]


async def distinct_genres(db: AsyncIOMotorDatabase) -> list[str]:
    """Feature #111 — se den identiske funktion i movie_repository.py."""
    values = await db[COLLECTION].distinct("genres")
    return sorted({v for v in values if v}, key=str.casefold)


async def set_serial_number(db: AsyncIOMotorDatabase, tv_show_id: str, serial_number: int) -> None:
    await db[COLLECTION].update_one(
        {"_id": ObjectId(tv_show_id)}, {"$set": {"serial_number": serial_number}}
    )


async def clear_serial_number(db: AsyncIOMotorDatabase, tv_show_id: str) -> None:
    await db[COLLECTION].update_one(
        {"_id": ObjectId(tv_show_id)}, {"$unset": {"serial_number": ""}}
    )


def _build_find_many_filter(
    query: str | None,
    normalized_tags: list[str] | None,
    formats: list[str] | None = None,
    audio_types: list[str] | None = None,
    media_types: list[str] | None = None,
    is_wishlist: bool = False,
    watched: bool | None = None,
    genres: list[str] | None = None,
) -> dict:
    """Shared by `find_many`/`count_many` (feature #15) so the two can never
    drift apart on what counts as a match."""
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
        filter_["genres"] = {"$in": genres}
    if watched is not None:
        filter_["watched"] = True if watched else {"$ne": True}
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
    skip: int = 0,
    limit: int | None = None,
    genres: list[str] | None = None,
) -> list[dict]:
    """`limit=None` (the default) fetches every match, no cap — used by
    callers that need the whole filtered set (Print-siden, Voldby BIO's
    søgning). `tv_show_service.list_tv_shows` passes a real `limit` for the
    paginated library view (feature #15), which used to be silently capped
    at 500 with no way to see or reach anything past it."""
    filter_ = _build_find_many_filter(
        query, normalized_tags, formats, audio_types, media_types, is_wishlist, watched, genres
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
    genres: list[str] | None = None,
) -> int:
    filter_ = _build_find_many_filter(
        query, normalized_tags, formats, audio_types, media_types, is_wishlist, watched, genres
    )
    return await db[COLLECTION].count_documents(filter_)


async def update(db: AsyncIOMotorDatabase, tv_show_id: str, fields: dict) -> dict | None:
    if not ObjectId.is_valid(tv_show_id):
        return None
    await db[COLLECTION].update_one({"_id": ObjectId(tv_show_id)}, {"$set": fields})
    return await db[COLLECTION].find_one({"_id": ObjectId(tv_show_id)})


async def delete(db: AsyncIOMotorDatabase, tv_show_id: str) -> bool:
    if not ObjectId.is_valid(tv_show_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(tv_show_id)})
    return result.deleted_count > 0


async def archive_deleted(db: AsyncIOMotorDatabase, tv_show_doc: dict, deleted_by: str) -> None:
    await db[DELETED_COLLECTION].insert_one(
        {
            "tv_show_id": tv_show_doc["_id"],
            "serial_number": tv_show_doc.get("serial_number"),
            "name": tv_show_doc["name"],
            "year": tv_show_doc.get("year"),
            "format": tv_show_doc.get("format"),
            "deleted_at": datetime.now(timezone.utc),
            "deleted_by": deleted_by,
        }
    )


async def list_deleted(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db[DELETED_COLLECTION].find().sort("deleted_at", -1)
    return await cursor.to_list(length=1000)


async def set_season_owned(db: AsyncIOMotorDatabase, tv_show_id: str, season_number: int, owned: bool) -> bool:
    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(tv_show_id), "seasons.season_number": season_number},
        {"$set": {"seasons.$.owned": owned}},
    )
    return result.matched_count > 0


async def set_season_episodes(
    db: AsyncIOMotorDatabase, tv_show_id: str, season_number: int, episodes: list[dict]
) -> bool:
    """Atomically replaces one season's *entire* episode list via the
    positional `$` update operator. Used only to populate a season right
    after its lazy TMDb fetch (a single write, nothing concurrent to race
    against) — see `set_episode_watched` below for toggling one episode,
    which must not use this "read the whole list, mutate one entry,
    write the whole list back" shape (see BUGS.md #25)."""
    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(tv_show_id), "seasons.season_number": season_number},
        {"$set": {"seasons.$.episodes": episodes}},
    )
    return result.matched_count > 0


async def set_episode_watched(
    db: AsyncIOMotorDatabase,
    tv_show_id: str,
    season_index: int,
    episode_index: int,
    watched: bool,
    watched_at,
) -> bool:
    """Atomically updates a single episode's watched-status via a numeric
    array-index path (`seasons.<i>.episodes.<j>.watched`) instead of
    reading the season's whole episode list, mutating one entry, and
    writing the whole list back — that read-modify-write shape lost writes
    under concurrent toggles of different episodes (BUGS.md #25, verified
    empirically: two concurrent toggles landed as `{1: False, 2: True}`
    instead of both `True`). Deliberately avoids the positional `$`/
    `arrayFilters` operators for this, which mongomock does not implement
    at all (confirmed directly — raises `NotImplementedError` — not just
    "inconsistent" as movie_repository's label-migration note assumed for a
    different, single-level case). The caller resolves `season_index`/
    `episode_index` from `season_number`/`episode_number` — safe because
    seasons/episodes are never reordered after being written once from
    TMDb, so two concurrent calls addressing different episodes always
    resolve to different, stable index paths and never clobber each
    other."""
    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(tv_show_id)},
        {
            "$set": {
                f"seasons.{season_index}.episodes.{episode_index}.watched": watched,
                f"seasons.{season_index}.episodes.{episode_index}.watched_at": watched_at,
            }
        },
    )
    return result.matched_count > 0
