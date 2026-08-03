from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.mongo_json import from_json_safe, to_json_safe
from app.core.version_info import VERSION_INFO
from app.models.backup import DatabaseResetResult, SystemBackup, SystemRestoreResult
from app.repositories import (
    movie_repository,
    screening_repository,
    screening_request_repository,
    tag_repository,
    tv_show_repository,
    user_repository,
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
    afterwards."""
    movies = await movie_repository.find_all_raw(db)
    tv_shows = await tv_show_repository.find_all_raw(db)
    deleted_movies = await db[movie_repository.DELETED_COLLECTION].find({}).to_list(length=None)
    deleted_tv_shows = await db[tv_show_repository.DELETED_COLLECTION].find({}).to_list(length=None)
    tags = await tag_repository.find_all_raw(db)
    users = await user_repository.find_all_raw(db)
    counters = await db[_COUNTERS_COLLECTION].find({}).to_list(length=None)

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
    )


async def _replace_raw_collection(db: AsyncIOMotorDatabase, name: str, documents: list[dict]) -> None:
    await db[name].delete_many({})
    if documents:
        await db[name].insert_many(documents)


async def restore_backup(db: AsyncIOMotorDatabase, backup: SystemBackup) -> SystemRestoreResult:
    """Wholesale-replaces every included collection with the backup's
    contents. Not transactional (standalone MongoDB, no replica set) — a
    failure partway through leaves some collections restored and others
    not; processed in a fixed order so a partial failure is at least
    predictable. `system_settings` is untouched (see `create_backup`)."""
    movies = [from_json_safe(doc) for doc in backup.movies]
    tv_shows = [from_json_safe(doc) for doc in backup.tv_shows]
    deleted_movies = [from_json_safe(doc) for doc in backup.deleted_movies]
    deleted_tv_shows = [from_json_safe(doc) for doc in backup.deleted_tv_shows]
    tags = [from_json_safe(doc) for doc in backup.tags]
    users = [from_json_safe(doc) for doc in backup.users]
    counters = [from_json_safe(doc) for doc in backup.counters]

    await movie_repository.replace_all(db, movies)
    await tv_show_repository.replace_all(db, tv_shows)
    await _replace_raw_collection(db, movie_repository.DELETED_COLLECTION, deleted_movies)
    await _replace_raw_collection(db, tv_show_repository.DELETED_COLLECTION, deleted_tv_shows)
    await tag_repository.replace_all(db, tags)
    await user_repository.replace_all(db, users)
    await _replace_raw_collection(db, _COUNTERS_COLLECTION, counters)

    return SystemRestoreResult(
        movies_imported=len(movies),
        tv_shows_imported=len(tv_shows),
        deleted_movies_imported=len(deleted_movies),
        deleted_tv_shows_imported=len(deleted_tv_shows),
        tags_imported=len(tags),
        users_imported=len(users),
        counters_imported=len(counters),
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
    Deliberately does NOT touch `users` or `system_settings` — this is a
    library reset, not a factory reset of the whole app."""
    movies_removed = await _clear_collection(db, movie_repository.COLLECTION)
    tv_shows_removed = await _clear_collection(db, tv_show_repository.COLLECTION)
    deleted_movies_removed = await _clear_collection(db, movie_repository.DELETED_COLLECTION)
    deleted_tv_shows_removed = await _clear_collection(db, tv_show_repository.DELETED_COLLECTION)
    tags_removed = await _clear_collection(db, tag_repository.COLLECTION)
    counters_removed = await _clear_collection(db, _COUNTERS_COLLECTION)
    screenings_removed = await _clear_collection(db, screening_repository.COLLECTION)
    screening_requests_removed = await _clear_collection(db, screening_request_repository.COLLECTION)

    return DatabaseResetResult(
        movies_removed=movies_removed,
        tv_shows_removed=tv_shows_removed,
        deleted_movies_removed=deleted_movies_removed,
        deleted_tv_shows_removed=deleted_tv_shows_removed,
        tags_removed=tags_removed,
        counters_removed=counters_removed,
        screenings_removed=screenings_removed,
        screening_requests_removed=screening_requests_removed,
    )
