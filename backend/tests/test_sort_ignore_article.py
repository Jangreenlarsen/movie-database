"""Feature #184 (Jan: "i sortering skal det være muligt at ignorerer 'the'
i starten af titel navn"). Dækker den rene streng-transformation
(`strip_leading_article`), at oprettelse/redigering holder `sort_title`/
`sort_name` ved lige, selve sorteringen via API'et, og migrations-
backfillet for dokumenter oprettet før feltet fandtes.
"""

from bson import ObjectId

from app.repositories import movie_repository, tv_show_repository
from app.repositories.sort_title import strip_leading_article


# --- strip_leading_article (ren funktion) ------------------------------------


def test_strips_the_case_insensitively():
    assert strip_leading_article("The Matrix") == "Matrix"
    assert strip_leading_article("the matrix") == "matrix"
    assert strip_leading_article("THE MATRIX") == "MATRIX"


def test_strips_multiple_spaces_entirely():
    assert strip_leading_article("The   Matrix") == "Matrix"


def test_leaves_titles_without_a_leading_article_unchanged():
    assert strip_leading_article("Amadeus") == "Amadeus"


def test_does_not_strip_words_that_merely_start_with_the_letters():
    # "the" uden et mellemrum bagefter er ikke artiklen "the" — ellers ville
    # "Thereafter"/"Theory" miste deres første tre bogstaver.
    assert strip_leading_article("Thereafter") == "Thereafter"
    assert strip_leading_article("Theory of Everything") == "Theory of Everything"


def test_the_alone_with_nothing_after_it_is_left_unchanged():
    # Intet mellemrum efter "The" her heller (det ER hele strengen) — samme
    # regel som ovenfor forhindrer et tomt, usorterbart resultat.
    assert strip_leading_article("The") == "The"


def test_only_strips_the_not_a_or_an():
    # Jan bad specifikt om "the" — a/an er bevidst ikke inkluderet.
    assert strip_leading_article("A Beautiful Mind") == "A Beautiful Mind"
    assert strip_leading_article("An American Tail") == "An American Tail"


# --- Film: oprettelse/redigering holder sort_title ved lige ------------------


async def test_creating_a_movie_computes_sort_title(client, db):
    response = await client.post(
        "/api/movies",
        json={"title": "The Godfather", "media_type": "Fysisk", "format": "F-DVD"},
    )
    movie_id = response.json()["id"]

    raw_doc = await db["movies"].find_one({"_id": ObjectId(movie_id)})
    assert raw_doc["sort_title"] == "Godfather"


async def test_editing_the_title_recomputes_sort_title(client, db):
    response = await client.post(
        "/api/movies", json={"title": "Amadeus", "media_type": "Fysisk", "format": "F-DVD"}
    )
    movie_id = response.json()["id"]

    await client.patch(f"/api/movies/{movie_id}", json={"title": "The Sting"})

    raw_doc = await db["movies"].find_one({"_id": ObjectId(movie_id)})
    assert raw_doc["sort_title"] == "Sting"


async def test_editing_unrelated_fields_leaves_sort_title_untouched(client, db):
    response = await client.post(
        "/api/movies", json={"title": "The Godfather", "media_type": "Fysisk", "format": "F-DVD"}
    )
    movie_id = response.json()["id"]

    await client.patch(f"/api/movies/{movie_id}", json={"year": 1972})

    raw_doc = await db["movies"].find_one({"_id": ObjectId(movie_id)})
    assert raw_doc["sort_title"] == "Godfather"


async def test_sorting_movies_by_title_no_article(client):
    # Plain "title" would put "Banana" before "The Aardvark" (B < T) — the
    # whole point of "title_no_article" is that stripping "The" flips this:
    # "Aardvark" < "Banana".
    await client.post(
        "/api/movies", json={"title": "The Aardvark", "media_type": "Fysisk", "format": "F-DVD"}
    )
    await client.post(
        "/api/movies", json={"title": "Banana", "media_type": "Fysisk", "format": "F-DVD"}
    )

    plain = await client.get("/api/movies", params={"sort": "title:asc"})
    assert [m["title"] for m in plain.json()["items"]] == ["Banana", "The Aardvark"]

    ignoring_article = await client.get("/api/movies", params={"sort": "title_no_article:asc"})
    assert [m["title"] for m in ignoring_article.json()["items"]] == ["The Aardvark", "Banana"]


# --- TV-serier: samme dækning, spejlet ---------------------------------------


async def test_creating_a_tv_show_computes_sort_name(client, db):
    response = await client.post(
        "/api/tv-shows", json={"name": "The Wire", "media_type": "Fysisk", "format": "F-DVD"}
    )
    show_id = response.json()["id"]

    raw_doc = await db["tv_shows"].find_one({"_id": ObjectId(show_id)})
    assert raw_doc["sort_name"] == "Wire"


async def test_editing_the_name_recomputes_sort_name(client, db):
    response = await client.post(
        "/api/tv-shows", json={"name": "Fargo", "media_type": "Fysisk", "format": "F-DVD"}
    )
    show_id = response.json()["id"]

    await client.patch(f"/api/tv-shows/{show_id}", json={"name": "The Wire"})

    raw_doc = await db["tv_shows"].find_one({"_id": ObjectId(show_id)})
    assert raw_doc["sort_name"] == "Wire"


async def test_sorting_tv_shows_by_name_no_article(client):
    await client.post(
        "/api/tv-shows", json={"name": "The Aardvark Show", "media_type": "Fysisk", "format": "F-DVD"}
    )
    await client.post(
        "/api/tv-shows", json={"name": "Banana Show", "media_type": "Fysisk", "format": "F-DVD"}
    )

    plain = await client.get("/api/tv-shows", params={"sort": "name:asc"})
    assert [s["name"] for s in plain.json()["items"]] == ["Banana Show", "The Aardvark Show"]

    ignoring_article = await client.get("/api/tv-shows", params={"sort": "name_no_article:asc"})
    assert [s["name"] for s in ignoring_article.json()["items"]] == [
        "The Aardvark Show",
        "Banana Show",
    ]


# --- Migration: backfill af dokumenter oprettet før feltet fandtes ----------


async def test_migration_backfills_sort_title_on_legacy_movie_documents(db):
    # Simulerer et dokument fra før feature #184 — indsat direkte, uden om
    # movie_service, så det ikke har sort_title.
    result = await db["movies"].insert_one({"title": "The Legacy Film"})
    assert "sort_title" not in await db["movies"].find_one({"_id": result.inserted_id})

    await movie_repository.ensure_indexes(db)

    raw_doc = await db["movies"].find_one({"_id": result.inserted_id})
    assert raw_doc["sort_title"] == "Legacy Film"


async def test_migration_backfills_sort_name_on_legacy_tv_show_documents(db):
    result = await db["tv_shows"].insert_one({"name": "The Legacy Show"})
    assert "sort_name" not in await db["tv_shows"].find_one({"_id": result.inserted_id})

    await tv_show_repository.ensure_indexes(db)

    raw_doc = await db["tv_shows"].find_one({"_id": result.inserted_id})
    assert raw_doc["sort_name"] == "Legacy Show"


async def test_migration_is_idempotent_and_does_not_touch_already_migrated_documents(db):
    result = await db["movies"].insert_one({"title": "The Idempotent Film", "sort_title": "already set"})

    await movie_repository.ensure_indexes(db)

    raw_doc = await db["movies"].find_one({"_id": result.inserted_id})
    assert raw_doc["sort_title"] == "already set"
