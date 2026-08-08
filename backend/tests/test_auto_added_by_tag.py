async def test_manually_created_movie_gets_added_by_tag(client):
    response = await client.post("/api/movies", json={"title": "Manual Movie", "media_type": "Fysisk", "format": "DVD"})
    assert response.json()["tags"] == ["Tilføjet af testuser"]


async def test_tmdb_created_movie_gets_added_by_tag(client, monkeypatch):
    from app.integrations import tmdb_client

    async def fake_get_movie_details(tmdb_id):
        return {
            "tmdb_id": tmdb_id,
            "title": "TMDb Movie",
            "year": 2020,
            "poster_url": None,
            "overview": None,
            "genres": [],
            "cast": [],
            "director": None,
            "collection_id": None,
            "collection_name": None,
            "rating": None,
            "runtime": None,
            "imdb_url": None,
            "trailer_url": None,
        }

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)

    response = await client.post("/api/movies", json={"tmdb_id": 1, "media_type": "Fysisk", "format": "DVD"})
    assert response.json()["tags"] == ["Tilføjet af testuser"]


async def test_manually_created_tv_show_gets_added_by_tag(client):
    response = await client.post("/api/tv-shows", json={"name": "Manual Show", "media_type": "Fysisk", "format": "DVD"})
    assert response.json()["tags"] == ["Tilføjet af testuser"]


async def test_added_by_tag_not_duplicated_across_creations_by_same_user(client):
    await client.post("/api/movies", json={"title": "First", "media_type": "Fysisk", "format": "DVD"})
    await client.post("/api/movies", json={"title": "Second", "media_type": "Fysisk", "format": "DVD"})

    tags = await client.get("/api/tags")
    assert tags.json().count("Tilføjet af testuser") == 1


async def test_added_by_tag_reflects_the_actual_creator_not_admin(client):
    """A second, active user's own creation should be tagged with *their*
    username, not the admin's."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second:
        register = await second.post(
            "/api/auth/register", json={"username": "otheruser", "password": "testpassword123"}
        )
        await client.patch(
            f"/api/users/{register.json()['id']}/status", json={"status": "active"}
        )
        response = await second.post("/api/movies", json={"title": "Other User's Movie", "media_type": "Fysisk", "format": "DVD"})
        assert response.json()["tags"] == ["Tilføjet af otheruser"]


async def test_updating_a_movie_does_not_add_or_duplicate_the_tag(client):
    created = await client.post("/api/movies", json={"title": "Editable Movie", "media_type": "Fysisk", "format": "DVD"})
    movie_id = created.json()["id"]
    assert created.json()["tags"] == ["Tilføjet af testuser"]

    updated = await client.patch(f"/api/movies/{movie_id}", json={"tags": ["Tilføjet af testuser"]})
    assert updated.json()["tags"] == ["Tilføjet af testuser"]


async def test_user_can_remove_the_added_by_tag_afterwards(client):
    """It's a normal tag once created, not specially protected — a user can
    still remove it via a regular tags update if they don't want it."""
    created = await client.post("/api/movies", json={"title": "Untaggable Movie", "media_type": "Fysisk", "format": "DVD"})
    movie_id = created.json()["id"]

    updated = await client.patch(f"/api/movies/{movie_id}", json={"tags": []})
    assert updated.json()["tags"] == []
