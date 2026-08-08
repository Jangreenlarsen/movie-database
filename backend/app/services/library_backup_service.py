import asyncio
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.mongo_json import from_json_safe, to_json_safe
from app.core.version_info import VERSION_INFO
from app.models.backup import (
    LibraryCounts,
    LibraryExport,
    LibraryImportResult,
    MediaTypeCounts,
)
from app.repositories import movie_repository, tv_show_repository


async def export_library(db: AsyncIOMotorDatabase) -> LibraryExport:
    movies = await movie_repository.find_all_raw(db)
    tv_shows = await tv_show_repository.find_all_raw(db)
    return LibraryExport(
        exported_at=datetime.now(timezone.utc),
        app_version=VERSION_INFO["version"],
        movies=[to_json_safe(doc) for doc in movies],
        tv_shows=[to_json_safe(doc) for doc in tv_shows],
    )


async def import_library(
    db: AsyncIOMotorDatabase, movies: list[dict], tv_shows: list[dict]
) -> LibraryImportResult:
    """Wholesale-replaces the `movies` and `tv_shows` collections with the
    given snapshot (feature #60) — for disaster recovery after the library
    itself gets messed up, or for moving a collection to another instance
    of this app. Does not touch `tags`/`deleted_movies`/`deleted_tv_shows`
    — see FEATURES.md #60/#61 for what a *full system* restore covers."""
    movie_docs = [from_json_safe(doc) for doc in movies]
    tv_show_docs = [from_json_safe(doc) for doc in tv_shows]

    await movie_repository.replace_all(db, movie_docs)
    await movie_repository.bump_serial_counter_past(db, movie_docs)
    await tv_show_repository.replace_all(db, tv_show_docs)
    await tv_show_repository.bump_serial_counter_past(db, tv_show_docs)

    return LibraryImportResult(movies_imported=len(movie_docs), tv_shows_imported=len(tv_show_docs))


async def get_counts(db: AsyncIOMotorDatabase) -> LibraryCounts:
    """Feature #94 — samlet overblik over hvor meget der staar i biblioteket.

    Film og TV-serier taelles hver for sig; de er to bevidst adskilte
    ressourcer (CLAUDE.md), og et samlet tal ville skjule netop den opdeling
    resten af appen er bygget op om."""
    movies, tv_shows = await asyncio.gather(
        movie_repository.count_library_by_media_type(db),
        tv_show_repository.count_library_by_media_type(db),
    )
    return LibraryCounts(
        movies=MediaTypeCounts(**movies),
        tv_shows=MediaTypeCounts(**tv_shows),
    )
