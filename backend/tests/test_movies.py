async def test_create_and_get_movie(client):
    response = await client.post(
        "/api/movies",
        json={"title": "The Matrix", "year": 1999, "tags": ["Sci-Fi", "sci-fi", " Favorite "]},
    )
    assert response.status_code == 201
    movie = response.json()
    assert movie["title"] == "The Matrix"
    assert movie["tags"] == ["Sci-Fi", "Favorite"]

    get_response = await client.get(f"/api/movies/{movie['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "The Matrix"


async def test_get_missing_movie_returns_404(client):
    response = await client.get("/api/movies/000000000000000000000000")
    assert response.status_code == 404


async def test_get_invalid_id_returns_404(client):
    response = await client.get("/api/movies/not-an-object-id")
    assert response.status_code == 404


async def test_tag_reuses_canonical_casing_across_movies(client):
    await client.post("/api/movies", json={"title": "Movie A", "tags": ["Action"]})
    response = await client.post("/api/movies", json={"title": "Movie B", "tags": ["ACTION"]})
    assert response.json()["tags"] == ["Action"]

    tags_response = await client.get("/api/tags")
    assert tags_response.json() == ["Action"]


async def test_new_tag_survives_concurrent_insert_race(client, monkeypatch):
    """Regression test for BUGS.md #7. Simulates a concurrent request that
    wins the race and inserts the same brand-new tag first, by making our
    own insert raise the same DuplicateKeyError MongoDB's unique index
    would — resolve_tags must recover by re-reading, not crash."""
    from pymongo.errors import DuplicateKeyError

    from app.repositories import tag_repository

    original_insert = tag_repository.insert
    call_count = {"n": 0}

    async def flaky_insert(db, name, normalized):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Simulate a concurrent request already having inserted it.
            await original_insert(db, name, normalized)
            raise DuplicateKeyError("E11000 duplicate key")
        return await original_insert(db, name, normalized)

    monkeypatch.setattr(tag_repository, "insert", flaky_insert)

    response = await client.post(
        "/api/movies", json={"title": "Race Test", "tags": ["BrandNewTag"]}
    )
    assert response.status_code == 201
    assert response.json()["tags"] == ["BrandNewTag"]


async def test_filter_by_tag_is_case_insensitive(client):
    await client.post("/api/movies", json={"title": "Tagged", "tags": ["Christmas"]})
    await client.post("/api/movies", json={"title": "Untagged"})

    response = await client.get("/api/movies", params={"tags": "christmas"})
    titles = [m["title"] for m in response.json()]
    assert titles == ["Tagged"]


async def test_update_and_delete_movie(client):
    create_response = await client.post("/api/movies", json={"title": "Old Title"})
    movie_id = create_response.json()["id"]

    update_response = await client.patch(f"/api/movies/{movie_id}", json={"title": "New Title"})
    assert update_response.json()["title"] == "New Title"

    delete_response = await client.delete(f"/api/movies/{movie_id}")
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/movies/{movie_id}")
    assert get_response.status_code == 404


async def test_barcode_must_be_unique(client):
    await client.post("/api/movies", json={"title": "First", "barcode": "1234567890123"})
    with_duplicate = await client.post(
        "/api/movies", json={"title": "Second", "barcode": "1234567890123"}
    )
    assert with_duplicate.status_code == 409


async def test_multiple_movies_without_barcode_are_allowed(client):
    """Regression test: the sparse unique index on `barcode` only excludes
    documents where the field is entirely absent, not documents where it's
    explicitly null. Storing `barcode: None` for every barcode-less movie
    would make the unique index collide after the second one."""
    first = await client.post("/api/movies", json={"title": "No Barcode A"})
    second = await client.post("/api/movies", json={"title": "No Barcode B"})
    assert first.status_code == 201
    assert second.status_code == 201


async def test_movie_without_barcode_omits_field_entirely(client, db):
    from bson import ObjectId

    response = await client.post("/api/movies", json={"title": "No Barcode"})
    movie_id = response.json()["id"]

    raw_doc = await db["movies"].find_one({"_id": ObjectId(movie_id)})
    assert "barcode" not in raw_doc


async def test_multiple_movies_with_blank_barcode_are_allowed(client, db):
    """Regression test for BUGS.md #10 — an explicit blank/whitespace-only
    barcode must be treated the same as omitting it entirely, not stored as
    a literal empty string (which would collide on the unique index just
    like the null case fixed above)."""
    from bson import ObjectId

    first = await client.post("/api/movies", json={"title": "Blank A", "barcode": ""})
    second = await client.post("/api/movies", json={"title": "Blank B", "barcode": "   "})
    assert first.status_code == 201
    assert second.status_code == 201

    raw_doc = await db["movies"].find_one({"_id": ObjectId(first.json()["id"])})
    assert "barcode" not in raw_doc


async def test_serial_number_auto_increments(client):
    first = await client.post("/api/movies", json={"title": "First"})
    second = await client.post("/api/movies", json={"title": "Second"})

    assert first.json()["serial_number"] == 1
    assert second.json()["serial_number"] == 2


async def test_create_movie_with_format_and_audio_types(client):
    response = await client.post(
        "/api/movies",
        json={
            "title": "The Matrix",
            "format": "BD",
            "audio_types": ["DD5.1", "DTS"],
        },
    )
    assert response.status_code == 201
    movie = response.json()
    assert movie["format"] == "BD"
    assert movie["audio_types"] == ["DD5.1", "DTS"]


async def test_create_movie_rejects_invalid_format(client):
    response = await client.post(
        "/api/movies", json={"title": "Bad Format", "format": "Laserdisc"}
    )
    assert response.status_code == 422


async def test_create_movie_rejects_invalid_audio_type(client):
    response = await client.post(
        "/api/movies", json={"title": "Bad Audio", "audio_types": ["Surround-o-matic"]}
    )
    assert response.status_code == 422


async def test_filter_by_format_and_audio_type(client):
    await client.post(
        "/api/movies",
        json={"title": "Blu-ray DTS", "format": "BD", "audio_types": ["DTS"]},
    )
    await client.post(
        "/api/movies",
        json={"title": "DVD Stereo", "format": "DVD", "audio_types": ["Stereo"]},
    )

    by_format = await client.get("/api/movies", params={"format": "BD"})
    assert [m["title"] for m in by_format.json()] == ["Blu-ray DTS"]

    by_audio = await client.get("/api/movies", params={"audio_types": "Stereo"})
    assert [m["title"] for m in by_audio.json()] == ["DVD Stereo"]


async def test_media_type_roundtrip_and_filter(client):
    """Regression test for FEATURES.md #35."""
    physical = await client.post(
        "/api/movies", json={"title": "Physical Copy", "media_type": "Fysisk"}
    )
    assert physical.json()["media_type"] == "Fysisk"
    await client.post("/api/movies", json={"title": "Digital Copy", "media_type": "Digital"})

    by_media_type = await client.get("/api/movies", params={"media_types": "Digital"})
    assert [m["title"] for m in by_media_type.json()] == ["Digital Copy"]

    options = await client.get("/api/movies/attribute-options")
    assert options.json()["media_types"] == ["Fysisk", "Digital"]


async def test_sort_by_newly_added_fields(client):
    """Regression test: serial_number and created_at must be independently
    sortable (previously the frontend mislabeled serial_number as
    "Tilføjet"), and runtime/location/owner/registered_by must be sortable
    too — Jan asked to be able to sort by "all fields"."""
    await client.post(
        "/api/movies", json={"title": "B Movie", "runtime": 90, "location": "Loft", "owner": "anna"}
    )
    await client.post(
        "/api/movies", json={"title": "A Movie", "runtime": 150, "location": "Stue", "owner": "bo"}
    )

    by_runtime = await client.get("/api/movies", params={"sort": "runtime:asc"})
    assert [m["title"] for m in by_runtime.json()] == ["B Movie", "A Movie"]

    by_location = await client.get("/api/movies", params={"sort": "location:asc"})
    assert [m["title"] for m in by_location.json()] == ["B Movie", "A Movie"]

    by_owner = await client.get("/api/movies", params={"sort": "owner:asc"})
    assert [m["title"] for m in by_owner.json()] == ["B Movie", "A Movie"]

    by_registered_by = await client.get("/api/movies", params={"sort": "registered_by:asc"})
    assert len(by_registered_by.json()) == 2

    by_created_at = await client.get("/api/movies", params={"sort": "created_at:asc"})
    assert [m["title"] for m in by_created_at.json()] == ["B Movie", "A Movie"]


async def test_sort_by_title(client):
    await client.post("/api/movies", json={"title": "Zebra"})
    await client.post("/api/movies", json={"title": "Apple"})

    asc = await client.get("/api/movies", params={"sort": "title:asc"})
    assert [m["title"] for m in asc.json()] == ["Apple", "Zebra"]

    desc = await client.get("/api/movies", params={"sort": "title:desc"})
    assert [m["title"] for m in desc.json()] == ["Zebra", "Apple"]


async def test_sort_by_year(client):
    await client.post("/api/movies", json={"title": "Old", "year": 1980})
    await client.post("/api/movies", json={"title": "New", "year": 2020})

    response = await client.get("/api/movies", params={"sort": "year:asc"})
    assert [m["title"] for m in response.json()] == ["Old", "New"]


async def test_sort_by_serial_number(client):
    await client.post("/api/movies", json={"title": "First"})
    await client.post("/api/movies", json={"title": "Second"})

    response = await client.get("/api/movies", params={"sort": "serial_number:desc"})
    assert [m["title"] for m in response.json()] == ["Second", "First"]


async def test_multi_level_sort_falls_through_to_second_field(client):
    """Regression test for FEATURES.md #17/#27 — ties on the first level
    should be broken by the second level."""
    await client.post("/api/movies", json={"title": "Zeta", "format": "DVD"})
    await client.post("/api/movies", json={"title": "Alpha", "format": "DVD"})
    await client.post("/api/movies", json={"title": "Middle", "format": "BD"})

    response = await client.get(
        "/api/movies", params={"sort": "format:asc,title:asc"}
    )
    assert [m["title"] for m in response.json()] == ["Middle", "Alpha", "Zeta"]


async def test_sort_by_rating(client, monkeypatch):
    from app.integrations import tmdb_client

    async def fake_get_movie_details(tmdb_id):
        ratings = {1: 5.0, 2: 9.0}
        return {
            "tmdb_id": tmdb_id,
            "title": f"Movie {tmdb_id}",
            "year": 2000,
            "poster_url": None,
            "overview": None,
            "genres": [],
            "cast": [],
            "rating": ratings[tmdb_id],
            "runtime": None,
            "imdb_url": None,
            "trailer_url": None,
        }

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)

    await client.post("/api/movies", json={"tmdb_id": 1})
    await client.post("/api/movies", json={"tmdb_id": 2})

    response = await client.get("/api/movies", params={"sort": "rating:desc"})
    assert [m["rating"] for m in response.json()] == [9.0, 5.0]


async def test_sort_ignores_unknown_field_and_falls_back_to_default(client):
    """An unrecognized sort field is dropped rather than rejected — a saved
    preset referencing a since-removed field should degrade gracefully
    (see movie_service.parse_sort_param) instead of erroring the whole page."""
    await client.post("/api/movies", json={"title": "Movie"})
    response = await client.get("/api/movies", params={"sort": "invalid_field"})
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_sort_treats_unrecognized_direction_as_ascending(client):
    await client.post("/api/movies", json={"title": "Zebra"})
    await client.post("/api/movies", json={"title": "Apple"})

    response = await client.get("/api/movies", params={"sort": "title:sideways"})
    assert response.status_code == 200
    assert [m["title"] for m in response.json()] == ["Apple", "Zebra"]


async def test_update_movie_format_and_audio_types(client):
    create_response = await client.post("/api/movies", json={"title": "Upgradeable"})
    movie_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/movies/{movie_id}",
        json={"format": "UHD", "audio_types": ["Atmos"]},
    )
    assert update_response.status_code == 200
    assert update_response.json()["format"] == "UHD"
    assert update_response.json()["audio_types"] == ["Atmos"]


async def test_update_serial_number_swaps_with_conflicting_movie(client):
    first = await client.post("/api/movies", json={"title": "First"})
    second = await client.post("/api/movies", json={"title": "Second"})
    first_id = first.json()["id"]
    second_id = second.json()["id"]
    assert first.json()["serial_number"] == 1
    assert second.json()["serial_number"] == 2

    response = await client.patch(f"/api/movies/{first_id}", json={"serial_number": 2})
    assert response.status_code == 200
    assert response.json()["serial_number"] == 2

    swapped = await client.get(f"/api/movies/{second_id}")
    assert swapped.json()["serial_number"] == 1


async def test_update_serial_number_to_unused_value_does_not_swap(client):
    only = await client.post("/api/movies", json={"title": "Only"})
    only_id = only.json()["id"]

    response = await client.patch(f"/api/movies/{only_id}", json={"serial_number": 42})
    assert response.status_code == 200
    assert response.json()["serial_number"] == 42


async def test_update_serial_number_rejects_non_positive(client):
    created = await client.post("/api/movies", json={"title": "Foo"})
    movie_id = created.json()["id"]

    response = await client.patch(f"/api/movies/{movie_id}", json={"serial_number": 0})
    assert response.status_code == 422


async def test_attribute_options_endpoint(client):
    response = await client.get("/api/movies/attribute-options")
    assert response.status_code == 200
    data = response.json()
    assert "BD" in data["formats"]
    assert "Atmos" in data["audio_types"]
    assert data["media_types"] == ["Fysisk", "Digital"]
