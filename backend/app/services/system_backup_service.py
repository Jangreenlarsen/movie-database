from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import InvalidBackupError
from app.core.mongo_json import from_json_safe, to_json_safe
from app.core.version_info import VERSION_INFO
from app.models.backup import DatabaseResetResult, SystemBackup, SystemRestoreResult
from app.repositories import (
    audit_log_repository,
    message_repository,
    movie_repository,
    poster_cache_repository,
    reservation_repository,
    screening_repository,
    screening_request_repository,
    tag_repository,
    tv_show_repository,
    user_repository,
    visit_repository,
)

# `counters` isn't owned by any single domain repository — it's a shared
# low-level primitive (both movie_repository and tv_show_repository read/
# write it under their own document `_id`s). A full system backup/restore
# is itself a low-level, cross-cutting operation (akin to `mongodump`/
# `mongorestore`, not application business logic), so this service reaches
# the raw collection directly here rather than inventing an artificial
# repository owner for it.
_COUNTERS_COLLECTION = movie_repository.COUNTERS_COLLECTION


async def create_backup(db: AsyncIOMotorDatabase) -> SystemBackup:
    """Full low-level dump of every collection needed to restore the whole
    system — deliberately EXCLUDING `system_settings` (FEATURES.md #61):
    a genuinely complete dump would have to include the actual TMDb/UPC/
    Discogs/OMDb/Plex keys, which CLAUDE.md regel 6 forbids returning to
    the frontend under any circumstance. Restoring from this backup is
    therefore not 100% complete — those keys must be re-entered manually
    afterwards.

    CLAUDE.md regel 20 / BUGS.md #65 — screenings/screening_requests/
    seat_reservations/messages/audit_log/visits are read straight off their
    collections (same low-level pattern as deleted_movies/counters below)
    rather than through each repository's business-logic functions, since a
    full system backup is a mongodump-style operation, not application
    logic. Every collection here comes from the *same* snapshot, so cross-
    collection references (e.g. a reservation's screening_id) stay mutually
    consistent on restore without any special ordering.

    `poster_cache` (feature #153) is included for the same regel-20 reason:
    it's technically re-derivable from TMDb, but restoring onto a fresh
    install without it means every poster requires live internet again
    until someone happens to view each title once."""
    movies = await movie_repository.find_all_raw(db)
    tv_shows = await tv_show_repository.find_all_raw(db)
    deleted_movies = await db[movie_repository.DELETED_COLLECTION].find({}).to_list(length=None)
    deleted_tv_shows = await db[tv_show_repository.DELETED_COLLECTION].find({}).to_list(length=None)
    tags = await tag_repository.find_all_raw(db)
    users = await user_repository.find_all_raw(db)
    counters = await db[_COUNTERS_COLLECTION].find({}).to_list(length=None)
    screenings = await db[screening_repository.COLLECTION].find({}).to_list(length=None)
    screening_requests = await db[screening_request_repository.COLLECTION].find({}).to_list(length=None)
    seat_reservations = await db[reservation_repository.COLLECTION].find({}).to_list(length=None)
    messages = await db[message_repository.COLLECTION].find({}).to_list(length=None)
    audit_log = await db[audit_log_repository.COLLECTION].find({}).to_list(length=None)
    visits = await db[visit_repository.COLLECTION].find({}).to_list(length=None)
    poster_cache = await poster_cache_repository.find_all_raw(db)

    return SystemBackup(
        backed_up_at=datetime.now(timezone.utc),
        app_version=VERSION_INFO["version"],
        movies=[to_json_safe(doc) for doc in movies],
        tv_shows=[to_json_safe(doc) for doc in tv_shows],
        deleted_movies=[to_json_safe(doc) for doc in deleted_movies],
        deleted_tv_shows=[to_json_safe(doc) for doc in deleted_tv_shows],
        tags=[to_json_safe(doc) for doc in tags],
        users=[to_json_safe(doc) for doc in users],
        counters=[to_json_safe(doc) for doc in counters],
        screenings=[to_json_safe(doc) for doc in screenings],
        screening_requests=[to_json_safe(doc) for doc in screening_requests],
        seat_reservations=[to_json_safe(doc) for doc in seat_reservations],
        messages=[to_json_safe(doc) for doc in messages],
        audit_log=[to_json_safe(doc) for doc in audit_log],
        visits=[to_json_safe(doc) for doc in visits],
        poster_cache=[to_json_safe(doc) for doc in poster_cache],
    )


async def _replace_raw_collection(db: AsyncIOMotorDatabase, name: str, documents: list[dict]) -> None:
    await db[name].delete_many({})
    if documents:
        await db[name].insert_many(documents)


async def _merge_raw_collection(db: AsyncIOMotorDatabase, name: str, documents: list[dict]) -> int:
    """Insert-only: adds documents from the backup whose `_id` isn't already
    present, never deletes anything already in the live collection. Used
    for `audit_log` (BUGS.md #65) — it's an accountability trail, not
    ordinary application data, and a restore must never be able to erase
    part of its own record. Concretely: `create_backup` writes its snapshot
    *before* the "system_backup.created" entry for that very backup is
    logged, so that entry (and anything else logged between backup and
    restore) is never in the snapshot being restored — wholesale-replacing
    the collection would silently delete it. On a genuinely empty target
    (disaster recovery onto a fresh database) this behaves identically to a
    full restore, since there is nothing pre-existing to preserve."""
    if not documents:
        return 0
    existing_ids = {doc["_id"] async for doc in db[name].find({}, {"_id": 1})}
    to_insert = [doc for doc in documents if doc.get("_id") not in existing_ids]
    if to_insert:
        await db[name].insert_many(to_insert)
    return len(to_insert)


def _assert_restorable(backup: SystemBackup) -> None:
    """BUGS.md #41 — a restore is delete-everything-then-insert, so an
    payload that merely *parses* is not enough: every collection field on
    `SystemBackup` defaults to an empty list, which meant a truncated,
    corrupted or wrong-file upload passed validation and then silently
    destroyed every collection, reporting 200 OK with zero counts.

    Requiring at least one active admin is the invariant that matters:
    it rejects both the entirely-empty payload and the subtler case of a
    users list containing only pending/rejected/disabled accounts, either of
    which would leave nobody able to administer (or undo) the restore. It
    never rejects a genuine backup — any real snapshot necessarily contains
    the active admin who took it. An empty *library* stays perfectly legal;
    restoring a backup made before any films were added is a valid thing to
    want. Raised before the first delete, so a rejected restore is a no-op."""
    has_active_admin = any(
        doc.get("role") == "admin" and doc.get("status", "active") == "active"
        for doc in backup.users
    )
    if not has_active_admin:
        raise InvalidBackupError(
            "Filen indeholder ingen aktiv admin-bruger og ser derfor ikke ud til at være "
            "en gyldig system-backup. Gendannelsen er afbrudt, og intet er slettet — "
            "kontrollér at du valgte den rigtige fil, og at den ikke er beskadiget."
        )


async def restore_backup(db: AsyncIOMotorDatabase, backup: SystemBackup) -> SystemRestoreResult:
    """Wholesale-replaces every included collection with the backup's
    contents — EXCEPT `audit_log`, which is merged in insert-only (see
    `_merge_raw_collection`): it's the system's own accountability trail,
    and a restore must never be able to erase part of it, including the
    "system_backup.created" entry for the very backup being restored (that
    entry is logged after the snapshot was taken, so it can never be *in*
    the snapshot). Not transactional (standalone MongoDB, no replica set) —
    a failure partway through leaves some collections restored and others
    not; processed in a fixed order so a partial failure is at least
    predictable. `system_settings` is untouched (see `create_backup`)."""
    _assert_restorable(backup)

    movies = [from_json_safe(doc) for doc in backup.movies]
    tv_shows = [from_json_safe(doc) for doc in backup.tv_shows]
    deleted_movies = [from_json_safe(doc) for doc in backup.deleted_movies]
    deleted_tv_shows = [from_json_safe(doc) for doc in backup.deleted_tv_shows]
    tags = [from_json_safe(doc) for doc in backup.tags]
    users = [from_json_safe(doc) for doc in backup.users]
    counters = [from_json_safe(doc) for doc in backup.counters]
    screenings = [from_json_safe(doc) for doc in backup.screenings]
    screening_requests = [from_json_safe(doc) for doc in backup.screening_requests]
    seat_reservations = [from_json_safe(doc) for doc in backup.seat_reservations]
    messages = [from_json_safe(doc) for doc in backup.messages]
    audit_log = [from_json_safe(doc) for doc in backup.audit_log]
    visits = [from_json_safe(doc) for doc in backup.visits]
    poster_cache = [from_json_safe(doc) for doc in backup.poster_cache]

    await movie_repository.replace_all(db, movies)
    await tv_show_repository.replace_all(db, tv_shows)
    await _replace_raw_collection(db, movie_repository.DELETED_COLLECTION, deleted_movies)
    await _replace_raw_collection(db, tv_show_repository.DELETED_COLLECTION, deleted_tv_shows)
    await tag_repository.replace_all(db, tags)
    await user_repository.replace_all(db, users)
    await _replace_raw_collection(db, _COUNTERS_COLLECTION, counters)
    await _replace_raw_collection(db, screening_repository.COLLECTION, screenings)
    await _replace_raw_collection(db, screening_request_repository.COLLECTION, screening_requests)
    await _replace_raw_collection(db, reservation_repository.COLLECTION, seat_reservations)
    await _replace_raw_collection(db, message_repository.COLLECTION, messages)
    audit_log_imported = await _merge_raw_collection(db, audit_log_repository.COLLECTION, audit_log)
    await _replace_raw_collection(db, visit_repository.COLLECTION, visits)
    await _replace_raw_collection(db, poster_cache_repository.COLLECTION, poster_cache)

    return SystemRestoreResult(
        movies_imported=len(movies),
        tv_shows_imported=len(tv_shows),
        deleted_movies_imported=len(deleted_movies),
        deleted_tv_shows_imported=len(deleted_tv_shows),
        tags_imported=len(tags),
        users_imported=len(users),
        counters_imported=len(counters),
        screenings_imported=len(screenings),
        screening_requests_imported=len(screening_requests),
        seat_reservations_imported=len(seat_reservations),
        messages_imported=len(messages),
        audit_log_imported=audit_log_imported,
        visits_imported=len(visits),
        poster_cache_imported=len(poster_cache),
    )


async def _clear_collection(db: AsyncIOMotorDatabase, name: str) -> int:
    result = await db[name].delete_many({})
    return result.deleted_count


async def reset_library(db: AsyncIOMotorDatabase) -> DatabaseResetResult:
    """Feature #67 — wipes the film/TV library back to a fresh-install empty
    state: movies, TV shows, their soft-deleted logs, tags, and the serial
    number counters (which lazily recreate themselves starting back at 1 the
    next time a movie/TV show is created — see movie_repository.next_serial_
    number). Also clears Voldby BIO screenings/screening-requests, since
    otherwise they'd be left pointing at movie/tv_show ids that no longer
    exist (Jan's confirmed choice 2026-08-03 — "kun film/TV + relateret").
    Seat reservations (feature #133) are cleared alongside screenings for
    the same reason — a reservation references a screening_id, and would
    otherwise dangle once its screening is gone (BUGS.md #65). Deliberately
    does NOT touch `users`, `system_settings`, `messages`, `audit_log`,
    `visits` or `poster_cache` — this is a library reset, not a factory
    reset of the whole app, and none of those are library data.
    `poster_cache` specifically is keyed on TMDb (size, path), not on any
    movie/tv_show id, so it stays valid and reusable even across a reset
    (the same TMDb image is the same bytes regardless of which library
    entry references it)."""
    movies_removed = await _clear_collection(db, movie_repository.COLLECTION)
    tv_shows_removed = await _clear_collection(db, tv_show_repository.COLLECTION)
    deleted_movies_removed = await _clear_collection(db, movie_repository.DELETED_COLLECTION)
    deleted_tv_shows_removed = await _clear_collection(db, tv_show_repository.DELETED_COLLECTION)
    tags_removed = await _clear_collection(db, tag_repository.COLLECTION)
    counters_removed = await _clear_collection(db, _COUNTERS_COLLECTION)
    screenings_removed = await _clear_collection(db, screening_repository.COLLECTION)
    screening_requests_removed = await _clear_collection(db, screening_request_repository.COLLECTION)
    seat_reservations_removed = await _clear_collection(db, reservation_repository.COLLECTION)

    return DatabaseResetResult(
        movies_removed=movies_removed,
        tv_shows_removed=tv_shows_removed,
        deleted_movies_removed=deleted_movies_removed,
        deleted_tv_shows_removed=deleted_tv_shows_removed,
        tags_removed=tags_removed,
        counters_removed=counters_removed,
        screenings_removed=screenings_removed,
        screening_requests_removed=screening_requests_removed,
        seat_reservations_removed=seat_reservations_removed,
    )
