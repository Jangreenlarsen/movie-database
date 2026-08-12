async def test_new_movie_has_no_personal_rating_or_note(client):
    response = await client.post("/api/movies", json={"title": "Fresh", "media_type": "Fysisk", "format": "F-DVD"})
    assert response.json()["personal_rating"] is None
    assert response.json()["personal_note"] is None


async def test_set_personal_rating_and_note(client):
    created = await client.post("/api/movies", json={"title": "Rateable", "media_type": "Fysisk", "format": "F-DVD"})
    movie_id = created.json()["id"]

    response = await client.patch(
        f"/api/movies/{movie_id}",
        json={"personal_rating": 8, "personal_note": "Rigtig god genseer."},
    )
    assert response.status_code == 200
    assert response.json()["personal_rating"] == 8
    assert response.json()["personal_note"] == "Rigtig god genseer."


async def test_clear_personal_rating_and_note(client):
    created = await client.post("/api/movies", json={"title": "Clearable", "media_type": "Fysisk", "format": "F-DVD"})
    movie_id = created.json()["id"]
    await client.patch(f"/api/movies/{movie_id}", json={"personal_rating": 5, "personal_note": "note"})

    response = await client.patch(
        f"/api/movies/{movie_id}", json={"personal_rating": None, "personal_note": None}
    )
    assert response.status_code == 200
    assert response.json()["personal_rating"] is None
    assert response.json()["personal_note"] is None


async def test_personal_rating_rejects_out_of_range(client):
    created = await client.post("/api/movies", json={"title": "Bounded", "media_type": "Fysisk", "format": "F-DVD"})
    movie_id = created.json()["id"]

    too_high = await client.patch(f"/api/movies/{movie_id}", json={"personal_rating": 11})
    too_low = await client.patch(f"/api/movies/{movie_id}", json={"personal_rating": 0})
    assert too_high.status_code == 422
    assert too_low.status_code == 422


async def test_sorting_by_personal_rating(client):
    a = await client.post("/api/movies", json={"title": "A", "media_type": "Fysisk", "format": "F-DVD"})
    b = await client.post("/api/movies", json={"title": "B", "media_type": "Fysisk", "format": "F-DVD"})
    await client.patch(f"/api/movies/{a.json()['id']}", json={"personal_rating": 3})
    await client.patch(f"/api/movies/{b.json()['id']}", json={"personal_rating": 9})

    response = await client.get("/api/movies", params={"sort": "personal_rating:desc"})
    titles = [m["title"] for m in response.json()["items"]]
    assert titles.index("B") < titles.index("A")
