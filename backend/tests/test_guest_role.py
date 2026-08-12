from httpx import ASGITransport, AsyncClient

from app.main import app


async def _guest_client(admin_client, username="guestuser"):
    """Registers a fresh user, approves them (feature #66), promotes them
    to guest (feature #72), and returns a logged-in AsyncClient for them."""
    transport = ASGITransport(app=app)
    guest = AsyncClient(transport=transport, base_url="http://test")
    register = await guest.post(
        "/api/auth/register", json={"username": username, "password": "testpassword123"}
    )
    user_id = register.json()["id"]
    await admin_client.patch(f"/api/users/{user_id}/status", json={"status": "active"})
    await admin_client.patch(f"/api/users/{user_id}/role", json={"role": "guest"})
    return guest


async def test_guest_can_list_movies_and_tv_shows(client):
    await client.post("/api/movies", json={"title": "Visible Movie", "media_type": "Fysisk", "format": "F-DVD"})
    await client.post("/api/tv-shows", json={"name": "Visible Show", "media_type": "Fysisk", "format": "F-DVD"})
    guest = await _guest_client(client)

    movies = await guest.get("/api/movies")
    assert movies.status_code == 200
    assert len(movies.json()["items"]) == 1

    shows = await guest.get("/api/tv-shows")
    assert shows.status_code == 200
    assert len(shows.json()["items"]) == 1
    await guest.aclose()


async def test_guest_cannot_create_movie(client):
    guest = await _guest_client(client)
    response = await guest.post("/api/movies", json={"title": "Should Fail", "media_type": "Fysisk", "format": "F-DVD"})
    assert response.status_code == 403
    await guest.aclose()


async def test_guest_can_create_wishlist_movie(client):
    """Feature #116 — gæster må oprette ønsker, selvom de ikke må oprette
    bibliotekspost."""
    guest = await _guest_client(client)
    response = await guest.post(
        "/api/movies", json={"title": "Wanted Movie", "is_wishlist": True}
    )
    assert response.status_code == 201
    assert response.json()["is_wishlist"] is True
    await guest.aclose()


async def test_guest_can_create_wishlist_tv_show(client):
    guest = await _guest_client(client)
    response = await guest.post(
        "/api/tv-shows", json={"name": "Wanted Show", "is_wishlist": True}
    )
    assert response.status_code == 201
    assert response.json()["is_wishlist"] is True
    await guest.aclose()


async def test_guest_order_status_is_ignored_on_wishlist_create(client):
    """Feature #116 — order_status tvinges til None for gæster, uanset hvad de
    sender (håndhævet i backend, ikke kun i UI)."""
    guest = await _guest_client(client)
    response = await guest.post(
        "/api/movies",
        json={"title": "Sneaky Wish", "is_wishlist": True, "order_status": "Bestilt ved iMusic"},
    )
    assert response.status_code == 201
    assert response.json()["order_status"] is None
    await guest.aclose()


async def test_guest_cannot_update_or_delete_movie(client):
    created = await client.post("/api/movies", json={"title": "Protected Movie", "media_type": "Fysisk", "format": "F-DVD"})
    movie_id = created.json()["id"]
    guest = await _guest_client(client)

    update = await guest.patch(f"/api/movies/{movie_id}", json={"personal_rating": 10})
    assert update.status_code == 403

    delete = await guest.delete(f"/api/movies/{movie_id}")
    assert delete.status_code == 403
    await guest.aclose()


async def test_guest_cannot_create_update_or_delete_tv_show(client):
    created = await client.post("/api/tv-shows", json={"name": "Protected Show", "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]
    guest = await _guest_client(client)

    create = await guest.post("/api/tv-shows", json={"name": "Should Fail", "media_type": "Fysisk", "format": "F-DVD"})
    assert create.status_code == 403

    update = await guest.patch(f"/api/tv-shows/{show_id}", json={"personal_rating": 10})
    assert update.status_code == 403

    delete = await guest.delete(f"/api/tv-shows/{show_id}")
    assert delete.status_code == 403
    await guest.aclose()


async def test_guest_cannot_toggle_season_owned_or_episode_watched(client, monkeypatch):
    from app.integrations import tmdb_client

    async def fake_get_tv_show_details(tv_id):
        return {
            "tmdb_id": tv_id,
            "name": "Season Show",
            "year": 2020,
            "end_year": None,
            "status": "Ended",
            "poster_url": None,
            "overview": None,
            "genres": [],
            "cast": [],
            "creators": [],
            "number_of_seasons": 1,
            "number_of_episodes": 1,
            "imdb_url": None,
            "imdb_id": None,
            "rating": None,
            "seasons": [
                {"season_number": 1, "name": "Season 1", "episode_count": 1, "air_date": None, "poster_url": None}
            ],
        }

    async def fake_get_season_details(tv_id, season_number):
        return [{"episode_number": 1, "name": "Pilot", "air_date": None, "watched": False, "watched_at": None}]

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)
    monkeypatch.setattr(tmdb_client, "get_season_details", fake_get_season_details)

    created = await client.post("/api/tv-shows", json={"tmdb_id": 1, "media_type": "Fysisk", "format": "F-DVD"})
    show_id = created.json()["id"]
    guest = await _guest_client(client)

    season_response = await guest.patch(
        f"/api/tv-shows/{show_id}/seasons/1", json={"owned": True}
    )
    assert season_response.status_code == 403

    episode_response = await guest.patch(
        f"/api/tv-shows/{show_id}/seasons/1/episodes/1", json={"watched": True}
    )
    assert episode_response.status_code == 403
    await guest.aclose()


async def test_guest_can_request_screening(client):
    """Regression test for feature #72's later refinement (Jans explicit
    choice 2026-08-03): guests may request a screening for a title they
    find in the library — the one write action allowed for the read-only
    role, since it's how they'd take part in Voldby BIO at all."""
    created = await client.post("/api/movies", json={"title": "Requestable Movie", "media_type": "Fysisk", "format": "F-DVD"})
    movie_id = created.json()["id"]
    guest = await _guest_client(client)

    response = await guest.post(
        "/api/screening-requests", json={"media_kind": "movie", "movie_id": movie_id}
    )
    assert response.status_code == 201
    await guest.aclose()


async def test_guest_can_see_public_screenings_calendar(client):
    guest = await _guest_client(client)
    response = await guest.get("/api/screenings")
    assert response.status_code == 200
    await guest.aclose()


async def test_guest_can_change_own_password(client):
    guest = await _guest_client(client)
    response = await guest.post(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "newpassword456"},
    )
    assert response.status_code == 204
    await guest.aclose()


async def test_guest_can_update_own_view_settings(client):
    guest = await _guest_client(client)
    response = await guest.patch("/api/users/me/settings", json={"card_size": "large"})
    assert response.status_code == 200
    assert response.json()["settings"]["card_size"] == "large"
    await guest.aclose()


async def test_admin_can_promote_user_to_guest(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second:
        register = await second.post(
            "/api/auth/register", json={"username": "promotetoguest", "password": "testpassword123"}
        )
        user_id = register.json()["id"]

    response = await client.patch(f"/api/users/{user_id}/role", json={"role": "guest"})
    assert response.status_code == 200
    assert response.json()["role"] == "guest"
