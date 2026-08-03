from httpx import ASGITransport, AsyncClient

from app.main import app


async def _register(username: str) -> tuple[AsyncClient, dict]:
    """Returns a fresh, logged-in AsyncClient plus the register response body,
    for a client not yet approved by the caller."""
    transport = ASGITransport(app=app)
    ac = AsyncClient(transport=transport, base_url="http://test")
    response = await ac.post(
        "/api/auth/register", json={"username": username, "password": "testpassword123"}
    )
    return ac, response.json()


async def test_first_registered_user_is_active(raw_client):
    """Regression guard for CLAUDE.md regel 16 (lockout-princippet): the very
    first user must bootstrap straight to `active`, or no admin would ever
    exist to approve them — a permanent lockout."""
    response = await raw_client.post(
        "/api/auth/register", json={"username": "first", "password": "testpassword123"}
    )
    assert response.json()["status"] == "active"


async def test_second_registered_user_is_pending(client):
    """The `client` fixture registers the first (active admin) user."""
    second, body = await _register("secondperson")
    assert body["status"] == "pending"
    await second.aclose()


async def test_pending_user_is_blocked_from_protected_endpoints(client):
    second, _ = await _register("pendinguser")
    response = await second.get("/api/movies")
    assert response.status_code == 403
    assert "godkendelse" in response.json()["detail"]
    await second.aclose()


async def test_pending_user_can_still_see_own_status_via_me(client):
    second, _ = await _register("pendinguser2")
    response = await second.get("/api/users/me")
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    await second.aclose()


async def test_pending_user_can_still_log_out(client):
    second, _ = await _register("pendinguser3")
    response = await second.post("/api/auth/logout")
    assert response.status_code == 204
    await second.aclose()


async def test_admin_sees_pending_status_in_user_list(client):
    second, body = await _register("pendinguser4")
    listing = await client.get("/api/users")
    target = next(u for u in listing.json() if u["id"] == body["id"])
    assert target["status"] == "pending"
    await second.aclose()


async def test_approving_a_pending_user_grants_access(client):
    second, body = await _register("approveme")
    approve = await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})
    assert approve.status_code == 200
    assert approve.json()["status"] == "active"

    response = await second.get("/api/movies")
    assert response.status_code == 200
    await second.aclose()


async def test_rejecting_a_pending_user_keeps_them_blocked_with_clear_message(client):
    second, body = await _register("rejectme")
    reject = await client.patch(f"/api/users/{body['id']}/status", json={"status": "rejected"})
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    response = await second.get("/api/movies")
    assert response.status_code == 403
    assert "afvist" in response.json()["detail"]

    me = await second.get("/api/users/me")
    assert me.json()["status"] == "rejected"
    await second.aclose()


async def test_cannot_reject_an_already_active_user(client):
    """Regression guard: approve/reject must only apply to a currently
    `pending` user — otherwise a stray click could lock out an active user
    (or even the last admin) by mistake."""
    me = await client.get("/api/users/me")
    my_id = me.json()["id"]

    response = await client.patch(f"/api/users/{my_id}/status", json={"status": "rejected"})
    assert response.status_code == 409

    still_me = await client.get("/api/users/me")
    assert still_me.json()["status"] == "active"


async def test_updating_status_requires_admin(client):
    second, body = await _register("notadminapprover")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})

    response = await second.patch(f"/api/users/{body['id']}/status", json={"status": "active"})
    assert response.status_code == 403
    await second.aclose()


async def test_update_status_of_unknown_user_returns_404(client):
    response = await client.patch(
        "/api/users/000000000000000000000000/status", json={"status": "active"}
    )
    assert response.status_code == 404


async def test_approve_and_reject_are_audit_logged(client):
    approve_target, approve_body = await _register("auditapprove")
    await client.patch(f"/api/users/{approve_body['id']}/status", json={"status": "active"})
    await approve_target.aclose()

    reject_target, reject_body = await _register("auditreject")
    await client.patch(f"/api/users/{reject_body['id']}/status", json={"status": "rejected"})
    await reject_target.aclose()

    log = await client.get("/api/audit-log")
    actions = {(e["action"], e["detail"]) for e in log.json()["entries"]}
    assert ("user.approved", "auditapprove") in actions
    assert ("user.rejected", "auditreject") in actions
