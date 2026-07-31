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
            "format": "Blu-ray",
            "audio_types": ["Dolby Digital 5.1", "DTS"],
        },
    )
    assert response.status_code == 201
    movie = response.json()
    assert movie["format"] == "Blu-ray"
    assert movie["audio_types"] == ["Dolby Digital 5.1", "DTS"]


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
        json={"title": "Blu-ray DTS", "format": "Blu-ray", "audio_types": ["DTS"]},
    )
    await client.post(
        "/api/movies",
        json={"title": "DVD Stereo", "format": "DVD", "audio_types": ["Stereo"]},
    )

    by_format = await client.get("/api/movies", params={"format": "Blu-ray"})
    assert [m["title"] for m in by_format.json()] == ["Blu-ray DTS"]

    by_audio = await client.get("/api/movies", params={"audio_types": "Stereo"})
    assert [m["title"] for m in by_audio.json()] == ["DVD Stereo"]


async def test_update_movie_format_and_audio_types(client):
    create_response = await client.post("/api/movies", json={"title": "Upgradeable"})
    movie_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/movies/{movie_id}",
        json={"format": "4K Ultra HD", "audio_types": ["Dolby Atmos"]},
    )
    assert update_response.status_code == 200
    assert update_response.json()["format"] == "4K Ultra HD"
    assert update_response.json()["audio_types"] == ["Dolby Atmos"]


async def test_attribute_options_endpoint(client):
    response = await client.get("/api/movies/attribute-options")
    assert response.status_code == 200
    data = response.json()
    assert "Blu-ray" in data["formats"]
    assert "Dolby Atmos" in data["audio_types"]
