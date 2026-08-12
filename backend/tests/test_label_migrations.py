from datetime import datetime, timezone

from app.repositories import movie_repository, tv_show_repository


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
    # A bare pre-v0.22.0 "Digital" cascades through the whole label history in
    # the same call: "Digital" -> "Digital-HD" -> "D-HD" -> "D-1080" (v0.105.0).
    digital = await db[movie_repository.COLLECTION].find_one({"title": "Old Digital Movie"})
    assert digital["format"] == "D-1080"


async def test_migrates_old_audio_type_labels_to_new_short_ones(db):
    """Regression test for the v0.22.0 AudioType relabel."""
    now = datetime.now(timezone.utc)
    await db[movie_repository.COLLECTION].insert_one(
        {
            "title": "Old Audio Movie",
            # Dækker både det pre-v0.22.0 lange label og de v0.22.0-korte
            # DTS-HD-labels der blev omdøbt i v0.105.0 — alle skal ende på
            # slutværdien i ét dict-opslag.
            "audio_types": [
                "Dolby Digital 5.1",
                "DTS-HD Master Audio",
                "DTS-HD-M",
                "DTS-HD-MA-7.1",
                "DTS",
            ],
            "serial_number": 3,
            "created_at": now,
            "updated_at": now,
        }
    )

    await movie_repository._migrate_audio_type_labels(db)

    movie = await db[movie_repository.COLLECTION].find_one({"title": "Old Audio Movie"})
    assert movie["audio_types"] == ["DD5.1", "DTS-HD5.1", "DTS-HD5.1", "DTS-HD7.1", "DTS"]


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


async def test_migrates_digital_quality_tier_labels_to_new_short_ones(db):
    """Regression test for the v0.84.0 digital-tier relabel (Jans ønske:
    "Digital-HD" osv. skal hedde "D-HD" osv.)."""
    now = datetime.now(timezone.utc)
    for i, (title, old_format) in enumerate(
        [
            ("Old Digital UHD Movie", "Digital-UHD"),
            ("Old Digital HD Movie", "Digital-HD"),
            ("Old Digital STD Movie", "Digital-STD"),
        ],
        start=5,
    ):
        await db[movie_repository.COLLECTION].insert_one(
            {
                "title": title,
                "format": old_format,
                "audio_types": [],
                "serial_number": i,
                "created_at": now,
                "updated_at": now,
            }
        )

    await movie_repository._migrate_format_labels(db)

    for title, new_format in [
        ("Old Digital UHD Movie", "D-4K"),
        ("Old Digital HD Movie", "D-1080"),
        ("Old Digital STD Movie", "D-SD"),
    ]:
        movie = await db[movie_repository.COLLECTION].find_one({"title": title})
        assert movie["format"] == new_format


async def test_tv_shows_migrate_digital_quality_tier_labels_on_startup(db):
    """TV-serier fandtes ikke ved v0.22.0's første relabel, men kan sagtens
    have digitale format-værdier fra Plex-importen (feature #91) — de skal
    migreres på samme måde, via deres egen kopi af migrationen."""
    now = datetime.now(timezone.utc)
    await db[tv_show_repository.COLLECTION].insert_one(
        {
            "name": "Old Digital Show",
            "format": "Digital-UHD",
            "audio_types": [],
            "seasons": [],
            "created_at": now,
            "updated_at": now,
        }
    )

    await tv_show_repository.ensure_indexes(db)

    show = await db[tv_show_repository.COLLECTION].find_one({"name": "Old Digital Show"})
    assert show["format"] == "D-4K"


async def test_tv_shows_migrate_dts_hd_audio_labels_on_startup(db):
    """Feature v0.105.0 — TV-serier fik deres egen audio-migration for de nye
    DTS-HD-omdøbninger (de fandtes ikke ved v0.22.0's audio-relabel, men kan
    have de korte labels fra manuel indtastning eller feature #122)."""
    now = datetime.now(timezone.utc)
    await db[tv_show_repository.COLLECTION].insert_one(
        {
            "name": "Old Audio Show",
            "format": "D-1080",
            "audio_types": ["DTS-HD-M", "DTS-HD-MA-7.1", "Atmos"],
            "seasons": [],
            "created_at": now,
            "updated_at": now,
        }
    )

    await tv_show_repository.ensure_indexes(db)

    show = await db[tv_show_repository.COLLECTION].find_one({"name": "Old Audio Show"})
    assert show["audio_types"] == ["DTS-HD5.1", "DTS-HD7.1", "Atmos"]
