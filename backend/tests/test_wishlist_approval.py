"""Feature #144 — ønsker fra ikke-admins afventer admin-godkendelse."""

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


async def test_nonadmin_wishlist_is_pending(client):
    member = await _member(client, "wish_pending")
    resp = await member.post("/api/movies", json={"title": "Ønske", "is_wishlist": True})
    assert resp.status_code == 201
    assert resp.json()["wishlist_status"] == "pending"
    await member.aclose()


async def test_admin_wishlist_is_approved(client):
    resp = await client.post("/api/movies", json={"title": "Admin Ønske", "is_wishlist": True})
    assert resp.json()["wishlist_status"] == "approved"


async def test_library_item_has_no_wishlist_status(client):
    resp = await client.post(
        "/api/movies", json={"title": "Bib", "media_type": "Fysisk", "format": "F-DVD"}
    )
    assert resp.json()["wishlist_status"] is None


async def test_nonadmin_cannot_approve_wishlist(client):
    member = await _member(client, "wish_noapprove")
    created = await member.post("/api/movies", json={"title": "Ønske2", "is_wishlist": True})
    movie_id = created.json()["id"]
    resp = await member.patch(f"/api/movies/{movie_id}", json={"wishlist_status": "approved"})
    assert resp.status_code == 403
    await member.aclose()


async def test_admin_can_approve_wishlist(client):
    member = await _member(client, "wish_okapprove")
    created = await member.post("/api/movies", json={"title": "Ønske3", "is_wishlist": True})
    movie_id = created.json()["id"]
    resp = await client.patch(f"/api/movies/{movie_id}", json={"wishlist_status": "approved"})
    assert resp.status_code == 200
    assert resp.json()["wishlist_status"] == "approved"
    await member.aclose()


async def test_tv_wishlist_approval_flow(client):
    member = await _member(client, "wish_tv")
    created = await member.post("/api/tv-shows", json={"name": "TV Ønske", "is_wishlist": True})
    assert created.json()["wishlist_status"] == "pending"
    show_id = created.json()["id"]
    assert (
        await member.patch(f"/api/tv-shows/{show_id}", json={"wishlist_status": "approved"})
    ).status_code == 403
    approved = await client.patch(f"/api/tv-shows/{show_id}", json={"wishlist_status": "approved"})
    assert approved.json()["wishlist_status"] == "approved"
    await member.aclose()
