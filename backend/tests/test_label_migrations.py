from datetime import datetime, timezone

from app.repositories import movie_repository


async def test_migrates_old_format_labels_to_new_short_ones(db):
    """Regression test for the v0.22.0 MovieFormat relabel — existing
    documents (inserted before this version, bypassing enum validation)
    must be rewritten to the new labels on startup."""
    now = datetime.now(timezone.utc)
    await db[movie_repository.COLLECTION].insert_one(
        {
            "title": "Old Format Movie",
            "format": "Blu-ray",
            "audio_types": [],
            "serial_number": 1,
            "created_at": now,
            "updated_at": now,
        }
    )
    await db[movie_repository.COLLECTION].insert_one(
        {
            "title": "Old Digital Movie",
            "format": "Digital",
            "audio_types": [],
            "serial_number": 2,
            "created_at": now,
            "updated_at": now,
        }
    )

    await movie_repository._migrate_format_labels(db)

    blu_ray = await db[movie_repository.COLLECTION].find_one({"title": "Old Format Movie"})
    assert blu_ray["format"] == "BD"
    digital = await db[movie_repository.COLLECTION].find_one({"title": "Old Digital Movie"})
    assert digital["format"] == "Digital-HD"


async def test_migrates_old_audio_type_labels_to_new_short_ones(db):
    """Regression test for the v0.22.0 AudioType relabel."""
    now = datetime.now(timezone.utc)
    await db[movie_repository.COLLECTION].insert_one(
        {
            "title": "Old Audio Movie",
            "audio_types": ["Dolby Digital 5.1", "DTS-HD Master Audio", "DTS"],
            "serial_number": 3,
            "created_at": now,
            "updated_at": now,
        }
    )

    await movie_repository._migrate_audio_type_labels(db)

    movie = await db[movie_repository.COLLECTION].find_one({"title": "Old Audio Movie"})
    assert movie["audio_types"] == ["DD5.1", "DTS-HD-M", "DTS"]


async def test_ensure_indexes_runs_both_label_migrations(db):
    """The migrations must actually be wired into startup (`ensure_indexes`),
    not just exist as standalone functions."""
    now = datetime.now(timezone.utc)
    await db[movie_repository.COLLECTION].insert_one(
        {
            "title": "Startup Migrated Movie",
            "format": "4K Ultra HD",
            "audio_types": ["Dolby Atmos"],
            "serial_number": 4,
            "created_at": now,
            "updated_at": now,
        }
    )

    await movie_repository.ensure_indexes(db)

    movie = await db[movie_repository.COLLECTION].find_one({"title": "Startup Migrated Movie"})
    assert movie["format"] == "UHD"
    assert movie["audio_types"] == ["Atmos"]
