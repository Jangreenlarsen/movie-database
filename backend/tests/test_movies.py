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
