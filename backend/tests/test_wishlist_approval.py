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


# Feature #165 — "afvis ønske" (modparten til godkendelse), med besked til
# ønske-opretteren.


async def test_nonadmin_cannot_reject_wishlist(client):
    member = await _member(client, "wish_noreject")
    created = await member.post("/api/movies", json={"title": "AfvisTest1", "is_wishlist": True})
    movie_id = created.json()["id"]
    resp = await member.post(f"/api/movies/{movie_id}/reject-wish", json={"message": "Nej tak"})
    assert resp.status_code == 403
    await member.aclose()


async def test_admin_can_reject_wishlist_with_message(client):
    member = await _member(client, "wish_reject_msg")
    created = await member.post("/api/movies", json={"title": "AfvisTest2", "is_wishlist": True})
    movie_id = created.json()["id"]

    resp = await client.post(
        f"/api/movies/{movie_id}/reject-wish", json={"message": "Vi har den allerede på Plex."}
    )
    assert resp.status_code == 204

    # Ønsket er væk, ikke bare markeret afvist.
    assert (await client.get(f"/api/movies/{movie_id}")).status_code == 404

    inbox = (await member.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    assert "AfvisTest2" in inbox[0]["subject"]
    assert "Vi har den allerede på Plex." in inbox[0]["body"]
    await member.aclose()


async def test_admin_can_reject_wishlist_without_message(client):
    """Ingen begrundelse angivet — brugeren skal stadig have en besked, med
    en generisk tekst i stedet for en tom/manglende besked (regel 16)."""
    member = await _member(client, "wish_reject_nomsg")
    created = await member.post("/api/movies", json={"title": "AfvisTest3", "is_wishlist": True})
    movie_id = created.json()["id"]

    resp = await client.post(f"/api/movies/{movie_id}/reject-wish", json={})
    assert resp.status_code == 204

    inbox = (await member.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    assert inbox[0]["body"]
    await member.aclose()


async def test_reject_requires_pending_wishlist(client):
    member = await _member(client, "wish_reject_notpending")
    created = await member.post("/api/movies", json={"title": "AfvisTest4", "is_wishlist": True})
    movie_id = created.json()["id"]
    await client.patch(f"/api/movies/{movie_id}", json={"wishlist_status": "approved"})

    resp = await client.post(f"/api/movies/{movie_id}/reject-wish", json={})
    assert resp.status_code == 409
    # Stadig der — kun en pending wish kan afvises.
    assert (await client.get(f"/api/movies/{movie_id}")).status_code == 200
    await member.aclose()


async def test_reject_wishlist_cannot_target_library_item(client):
    created = await client.post(
        "/api/movies", json={"title": "AfvisTest5", "media_type": "Fysisk", "format": "F-DVD"}
    )
    movie_id = created.json()["id"]
    resp = await client.post(f"/api/movies/{movie_id}/reject-wish", json={})
    assert resp.status_code == 409


async def test_tv_wishlist_rejection_flow(client):
    member = await _member(client, "wish_tv_reject")
    created = await member.post("/api/tv-shows", json={"name": "TV Afvis", "is_wishlist": True})
    show_id = created.json()["id"]

    assert (
        await member.post(f"/api/tv-shows/{show_id}/reject-wish", json={})
    ).status_code == 403

    resp = await client.post(
        f"/api/tv-shows/{show_id}/reject-wish", json={"message": "For niche til biblioteket."}
    )
    assert resp.status_code == 204
    assert (await client.get(f"/api/tv-shows/{show_id}")).status_code == 404

    inbox = (await member.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    assert "For niche til biblioteket." in inbox[0]["body"]
    await member.aclose()
