async def test_owners_merges_and_dedupes_across_movies_and_tv_shows(client):
    await client.post("/api/movies", json={"title": "Movie A", "owner": "Jan"})
    await client.post("/api/movies", json={"title": "Movie B", "owner": "Anna"})
    await client.post("/api/tv-shows", json={"name": "Show A", "owner": "Jan"})
    # No explicit owner given — defaults to the registered creator ("testuser",
    # see conftest.py's `client` fixture), which must also show up as an
    # in-use value.
    await client.post("/api/movies", json={"title": "No Owner"})

    response = await client.get("/api/owners")
    assert response.status_code == 200
    assert response.json() == ["Anna", "Jan", "testuser"]


async def test_locations_merges_and_dedupes_across_movies_and_tv_shows(client):
    await client.post("/api/movies", json={"title": "Movie A", "location": "Stue"})
    await client.post("/api/tv-shows", json={"name": "Show A", "location": "Kælder"})
    await client.post("/api/tv-shows", json={"name": "Show B", "location": "Stue"})

    response = await client.get("/api/locations")
    assert response.status_code == 200
    assert response.json() == ["Kælder", "Stue"]


async def test_owners_empty_when_nothing_created(client):
    response = await client.get("/api/owners")
    assert response.json() == []


async def test_owners_requires_authentication(raw_client):
    response = await raw_client.get("/api/owners")
    assert response.status_code == 401
