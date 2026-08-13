"""Feature #141 — når et ønske flyttes fra indkøbslisten til biblioteket, får
den bruger der satte det på listen besked."""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _member(admin_client, name):
    transport = ASGITransport(app=app)
    member = AsyncClient(transport=transport, base_url="http://test")
    register = await member.post(
        "/api/auth/register", json={"username": name, "password": "testpassword123"}
    )
    await admin_client.patch(
        f"/api/users/{register.json()['id']}/status", json={"status": "active"}
    )
    return member


async def test_moving_wishlist_movie_to_library_notifies_the_adder(client):
    wisher = await _member(client, "movie_wisher")
    created = await wisher.post(
        "/api/movies", json={"title": "Ønsket Film", "is_wishlist": True}
    )
    movie_id = created.json()["id"]
    assert (await wisher.get("/api/messages/inbox")).json() == []

    # Admin (client) køber den og flytter den til biblioteket.
    resp = await client.patch(
        f"/api/movies/{movie_id}",
        json={"is_wishlist": False, "media_type": "Fysisk", "format": "F-DVD"},
    )
    assert resp.status_code == 200

    inbox = (await wisher.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    assert "Ønsket Film" in inbox[0]["body"]
    await wisher.aclose()


async def test_moving_wishlist_tv_to_library_notifies_the_adder(client):
    wisher = await _member(client, "tv_wisher")
    created = await wisher.post(
        "/api/tv-shows", json={"name": "Ønsket Serie", "is_wishlist": True}
    )
    show_id = created.json()["id"]

    resp = await client.patch(
        f"/api/tv-shows/{show_id}",
        json={"is_wishlist": False, "media_type": "Fysisk", "format": "F-DVD"},
    )
    assert resp.status_code == 200

    inbox = (await wisher.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    assert "Ønsket Serie" in inbox[0]["body"]
    await wisher.aclose()


async def test_no_self_notification_when_the_adder_moves_it_themselves(client):
    """Flytter man selv sit eget ønske til biblioteket, får man ikke besked om
    sin egen handling."""
    # `client` (testuser/admin) opretter OG flytter selv.
    created = await client.post(
        "/api/movies", json={"title": "Egen Film", "is_wishlist": True}
    )
    movie_id = created.json()["id"]
    await client.patch(
        f"/api/movies/{movie_id}",
        json={"is_wishlist": False, "media_type": "Fysisk", "format": "F-DVD"},
    )
    assert (await client.get("/api/messages/inbox")).json() == []
