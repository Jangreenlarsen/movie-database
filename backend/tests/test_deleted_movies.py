async def test_deleting_a_movie_logs_it_in_the_deleted_list(client):
    """Regression coverage for FEATURES.md #29 — deleting a movie must not
    just vanish it; it should be journalized with serial_number/title/who/when."""
    create = await client.post(
        "/api/movies", json={"title": "To Be Deleted", "year": 2001, "media_type": "Fysisk", "format": "DVD"}
    )
    movie = create.json()
    serial_number = movie["serial_number"]

    delete_response = await client.delete(f"/api/movies/{movie['id']}")
    assert delete_response.status_code == 204

    deleted_list = await client.get("/api/movies/deleted")
    assert deleted_list.status_code == 200
    entries = deleted_list.json()
    assert len(entries) == 1
    assert entries[0]["serial_number"] == serial_number
    assert entries[0]["title"] == "To Be Deleted"
    assert entries[0]["deleted_by"] == "testuser"


async def test_deleted_movies_serial_number_is_free_for_reuse(client):
    """Once a movie is deleted, a new movie's serial_number edit can reuse
    its now-free number — the unique index only tracks live movies."""
    create = await client.post("/api/movies", json={"title": "First", "media_type": "Fysisk", "format": "DVD"})
    first_movie = create.json()
    freed_serial = first_movie["serial_number"]

    await client.delete(f"/api/movies/{first_movie['id']}")

    second = await client.post("/api/movies", json={"title": "Second", "media_type": "Fysisk", "format": "DVD"})
    second_movie = second.json()

    response = await client.patch(
        f"/api/movies/{second_movie['id']}", json={"serial_number": freed_serial}
    )
    assert response.status_code == 200
    assert response.json()["serial_number"] == freed_serial


async def test_get_missing_movie_deletion_returns_404(client):
    response = await client.delete("/api/movies/000000000000000000000000")
    assert response.status_code == 404
