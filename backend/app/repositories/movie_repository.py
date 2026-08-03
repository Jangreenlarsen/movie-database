from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

COLLECTION = "movies"
DELETED_COLLECTION = "deleted_movies"
COUNTERS_COLLECTION = "counters"
SERIAL_COUNTER_ID = "movie_serial"
DEFAULT_SERIAL_CONFIG = {"next_value": 1, "increment": 1, "padding_width": 0}
MAX_SERIAL_ASSIGN_ATTEMPTS = 10_000

# Whitelist mapping API-facing sort keys -> actual document fields, so an
# arbitrary/unindexed field can never be requested via the query string.
SORT_FIELDS = {
    "title": "title",
    "year": "year",
    "serial_number": "serial_number",
    "created_at": "created_at",
    "rating": "rating",
    "personal_rating": "personal_rating",
    "runtime": "runtime",
    "format": "format",
    "audio_types": "audio_types",
    "media_type": "media_type",
    "location": "location",
    "owner": "owner",
    "registered_by": "registered_by",
    "watched_at": "watched_at",
}
DEFAULT_SORT_FIELD = "created_at"
MAX_SORT_LEVELS = 3

# Pre-v0.22.0 AudioType labels -> the new, shorter ones — see
# `_migrate_audio_type_labels` and `models/movie.py::AudioType`.
_AUDIO_TYPE_LABEL_MIGRATIONS = {
    "Dolby Digital": "DD",
    "Dolby Digital 5.1": "DD5.1",
    "Dolby Digital 7.1": "DD7.1",
    "DTS-HD Master Audio": "DTS-HD-M",
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
_FORMAT_LABEL_MIGRATIONS = {
    "Blu-ray": "BD",
    "4K Ultra HD": "UHD",
    "Digital": "Digital-HD",
}


async def _migrate_format_labels(db: AsyncIOMotorDatabase) -> None:
    """One-time rewrite of existing documents' `format` value from the old,
    longer labels to the new short ones — same rationale as
    `_migrate_audio_type_labels`, but `format` is a single field, not an
    array, so a plain `update_many` per old value suffices."""
    collection = db[COLLECTION]
    for old_label, new_label in _FORMAT_LABEL_MIGRATIONS.items():
        await collection.update_many({"format": old_label}, {"$set": {"format": new_label}})


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    collection = db[COLLECTION]
    await _migrate_audio_type_labels(db)
    await _migrate_format_labels(db)
    await collection.create_index([("title", "text"), ("overview", "text")])
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
    existing_indexes = await collection.index_information()
    serial_index = existing_indexes.get("serial_number_1")
    if serial_index is not None and not serial_index.get("sparse"):
        await collection.drop_index("serial_number_1")
    await collection.create_index("serial_number", unique=True, sparse=True)

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
    }


async def update_serial_config(db: AsyncIOMotorDatabase, updates: dict) -> dict:
    """`start_number` is a one-off "assign this to the next movie" action, not
    a historical origin — it directly moves the next-value pointer.
    `increment` only changes the step size going forward. `padding_width`
    is display-only."""
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
    return await get_serial_config(db)


async def next_serial_number(db: AsyncIOMotorDatabase) -> int:
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

        if await db[COLLECTION].find_one({"serial_number": candidate}, {"_id": 1}) is None:
            return candidate

    raise RuntimeError("Could not find a free serial number after many attempts")


async def insert(db: AsyncIOMotorDatabase, document: dict) -> dict:
    result = await db[COLLECTION].insert_one(document)
    return await db[COLLECTION].find_one({"_id": result.inserted_id})


async def find_by_id(db: AsyncIOMotorDatabase, movie_id: str) -> dict | None:
    if not ObjectId.is_valid(movie_id):
        return None
    return await db[COLLECTION].find_one({"_id": ObjectId(movie_id)})


async def find_by_serial_number(db: AsyncIOMotorDatabase, serial_number: int) -> dict | None:
    return await db[COLLECTION].find_one({"serial_number": serial_number})


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
) -> dict:
    """`is_wishlist=False` matches both `is_wishlist: false` *and* documents
    that predate this field entirely (`$ne: True`, not a `False` equality
    check) — see FEATURES.md #28 and BUGS.md's "check every representation
    of empty" lesson (CLAUDE.md regel 16). Shared by `find_many`/`count_many`
    (feature #15) so the two can never drift apart on what counts as a
    match."""
    filter_: dict = {"is_wishlist": True if is_wishlist else {"$ne": True}}
    if query:
        filter_["$text"] = {"$search": query}
    if normalized_tags:
        filter_["tags_normalized"] = {"$all": normalized_tags}
    if formats:
        filter_["format"] = {"$in": formats}
    if audio_types:
        filter_["audio_types"] = {"$in": audio_types}
    if media_types:
        filter_["media_type"] = {"$in": media_types}
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
        query, normalized_tags, formats, audio_types, media_types, is_wishlist, watched, cast, director
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
) -> int:
    filter_ = _build_find_many_filter(
        query, normalized_tags, formats, audio_types, media_types, is_wishlist, watched, cast, director
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
