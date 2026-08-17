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


# Feature #80 — disable/re-enable an already-active account.


async def test_disabling_an_active_user_blocks_them_with_clear_message(client):
    second, body = await _register("disableme")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})

    disable = await client.patch(f"/api/users/{body['id']}/status", json={"status": "disabled"})
    assert disable.status_code == 200
    assert disable.json()["status"] == "disabled"

    response = await second.get("/api/movies")
    assert response.status_code == 403
    assert "deaktiveret" in response.json()["detail"]
    await second.aclose()


async def test_reenabling_a_disabled_user_restores_access(client):
    second, body = await _register("reenableme")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "disabled"})

    reenable = await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})
    assert reenable.status_code == 200
    assert reenable.json()["status"] == "active"

    response = await second.get("/api/movies")
    assert response.status_code == 200
    await second.aclose()


async def test_cannot_disable_a_pending_user(client):
    """Disabling only applies to an already-active account — a pending
    registration should be approved/rejected instead (same class of guard
    as test_cannot_reject_an_already_active_user, just the mirror case)."""
    _, body = await _register("stillpending")
    response = await client.patch(f"/api/users/{body['id']}/status", json={"status": "disabled"})
    assert response.status_code == 409


async def test_cannot_activate_a_rejected_user(client):
    second, body = await _register("stayrejected")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "rejected"})

    response = await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})
    assert response.status_code == 409
    await second.aclose()


async def test_cannot_disable_self(client):
    me = await client.get("/api/users/me")
    response = await client.patch(f"/api/users/{me.json()['id']}/status", json={"status": "disabled"})
    assert response.status_code == 409


async def test_cannot_disable_the_last_active_admin(client, db):
    """The self-guard (test_cannot_disable_self) already blocks the only
    way to reach this scenario through the API — `require_admin` means
    whoever calls this endpoint while exactly one active admin exists must
    *be* that admin. The last-admin check is defense-in-depth for that
    same lockout class (CLAUDE.md regel 16), so it's exercised directly
    against the service layer instead, simulating a hypothetical caller
    distinct from the sole remaining admin."""
    from bson import ObjectId

    from app.core.errors import LastAdminError
    from app.services import auth_service

    me = await client.get("/api/users/me")
    my_id = me.json()["id"]

    fake_other_caller = str(ObjectId())
    try:
        await auth_service.update_user_status(db, my_id, "disabled", fake_other_caller)
        assert False, "expected LastAdminError"
    except LastAdminError:
        pass

    still_me = await client.get("/api/users/me")
    assert still_me.json()["status"] == "active"


async def test_disable_and_reenable_are_audit_logged(client):
    second, body = await _register("auditdisable")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "disabled"})
    await second.aclose()

    log = await client.get("/api/audit-log")
    actions = {(e["action"], e["detail"]) for e in log.json()["entries"]}
    assert ("user.disabled", "auditdisable") in actions


# Feature #80 — permanently delete a user.


async def test_admin_can_delete_a_user(client):
    second, body = await _register("deleteme")
    await second.aclose()

    response = await client.delete(f"/api/users/{body['id']}")
    assert response.status_code == 204

    listing = await client.get("/api/users")
    assert body["id"] not in [u["id"] for u in listing.json()]


async def test_deleting_a_user_lets_the_username_be_reused(client):
    """A hard delete, not a soft one — the username should be free again."""
    second, body = await _register("reusablename")
    await second.aclose()
    await client.delete(f"/api/users/{body['id']}")

    reregistered = await client.post(
        "/api/auth/register", json={"username": "reusablename", "password": "testpassword123"}
    )
    assert reregistered.status_code == 201


async def test_deleting_unknown_user_returns_404(client):
    response = await client.delete("/api/users/000000000000000000000000")
    assert response.status_code == 404


async def test_deleting_user_requires_admin(client):
    second, body = await _register("notadmindeleter")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})

    response = await second.delete(f"/api/users/{body['id']}")
    assert response.status_code == 403
    await second.aclose()


async def test_cannot_delete_self(client):
    me = await client.get("/api/users/me")
    response = await client.delete(f"/api/users/{me.json()['id']}")
    assert response.status_code == 409

    still_there = await client.get("/api/users")
    assert me.json()["id"] in [u["id"] for u in still_there.json()]


async def test_cannot_delete_the_last_active_admin(client, db):
    """Same reasoning as test_cannot_disable_the_last_active_admin — the
    self-guard already covers the only real-world path to this scenario,
    so the service-layer guard is exercised directly."""
    from bson import ObjectId

    from app.core.errors import LastAdminError
    from app.services import auth_service

    me = await client.get("/api/users/me")
    my_id = me.json()["id"]

    fake_other_caller = str(ObjectId())
    try:
        await auth_service.delete_user(db, my_id, fake_other_caller)
        assert False, "expected LastAdminError"
    except LastAdminError:
        pass

    still_there = await client.get("/api/users")
    assert my_id in [u["id"] for u in still_there.json()]


async def test_deletion_is_audit_logged(client):
    second, body = await _register("auditdelete")
    await second.aclose()
    await client.delete(f"/api/users/{body['id']}")

    log = await client.get("/api/audit-log")
    actions = {(e["action"], e["detail"]) for e in log.json()["entries"]}
    assert ("user.deleted", "auditdelete") in actions


# Feature #171 — admin-assisteret adgangskode-nulstilling (password recovery
# uden e-mail-system).


async def test_admin_can_reset_a_users_password(client):
    second, body = await _register("resetme")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})
    await second.aclose()

    resp = await client.post(f"/api/users/{body['id']}/reset-password")
    assert resp.status_code == 200
    result = resp.json()
    assert result["username"] == "resetme"
    assert len(result["new_password"]) >= 8

    # Den gamle adgangskode virker ikke længere; den nye gør.
    fresh = ASGITransport(app=app)
    async with AsyncClient(transport=fresh, base_url="http://test") as relogin:
        old_attempt = await relogin.post(
            "/api/auth/login", json={"username": "resetme", "password": "testpassword123"}
        )
        assert old_attempt.status_code == 401
        new_attempt = await relogin.post(
            "/api/auth/login", json={"username": "resetme", "password": result["new_password"]}
        )
        assert new_attempt.status_code == 200


async def test_reset_password_requires_admin(client):
    second, body = await _register("cannotreset")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})

    resp = await second.post(f"/api/users/{body['id']}/reset-password")
    assert resp.status_code == 403
    await second.aclose()


async def test_reset_password_unknown_user_returns_404(client):
    resp = await client.post("/api/users/000000000000000000000000/reset-password")
    assert resp.status_code == 404


async def test_reset_password_is_audit_logged_without_leaking_the_password(client):
    second, body = await _register("auditreset")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})
    await second.aclose()

    resp = await client.post(f"/api/users/{body['id']}/reset-password")
    new_password = resp.json()["new_password"]

    log = await client.get("/api/audit-log")
    actions = {(e["action"], e["detail"]) for e in log.json()["entries"]}
    assert ("user.password_reset", "auditreset") in actions
    # Regel 6-princippet anvendt på adgangskoder: selve værdien må aldrig stå
    # nogen steder i audit-loggen, kun AT en nulstilling skete.
    assert new_password not in log.text


# Feature #172 — tvunget adgangskodeskift efter en admin-nulstilling (Jans
# udtrykkelige krav: "det skal være udfravigeligt").


async def test_reset_password_forces_a_change_before_anything_else_works(client):
    second, body = await _register("mustchange172")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})

    resp = await client.post(f"/api/users/{body['id']}/reset-password")
    temp_password = resp.json()["new_password"]

    # Blokeret fra almindelige endpoints, med en tydelig besked — samme
    # mønster som pending/rejected/disabled ovenfor.
    blocked = await second.get("/api/movies")
    assert blocked.status_code == 403
    assert "skifte din adgangskode" in blocked.json()["detail"]

    # Men /users/me virker stadig — ellers en permanent lockout ingen,
    # heller ikke brugeren selv, kunne rette (CLAUDE.md regel 16).
    me = await second.get("/api/users/me")
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True

    # Selve skiftet virker på trods af blokeringen, og bruger den udstedte
    # midlertidige kode som nuværende adgangskode.
    changed = await second.post(
        "/api/users/me/password",
        json={"current_password": temp_password, "new_password": "myOwnNewPassword1"},
    )
    assert changed.status_code == 204

    # Blokeringen er væk med det samme, uden at skulle logge ind igen.
    unblocked = await second.get("/api/movies")
    assert unblocked.status_code == 200
    still_me = await second.get("/api/users/me")
    assert still_me.json()["must_change_password"] is False
    await second.aclose()


async def test_fresh_login_with_the_temporary_password_reflects_must_change_password(client):
    """En frisk login (mere realistisk end at genbruge en allerede åben
    session — brugeren har jo typisk ikke en aktiv session efter et reset)
    skal vise flaget med det samme."""
    second, body = await _register("freshlogin172")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})
    await second.aclose()

    resp = await client.post(f"/api/users/{body['id']}/reset-password")
    temp_password = resp.json()["new_password"]

    fresh = ASGITransport(app=app)
    async with AsyncClient(transport=fresh, base_url="http://test") as relogin:
        login = await relogin.post(
            "/api/auth/login", json={"username": "freshlogin172", "password": temp_password}
        )
        assert login.status_code == 200
        assert login.json()["must_change_password"] is True


async def test_voluntary_password_change_does_not_set_must_change_password(client):
    """En almindelig, selvvalgt adgangskodeskift (ikke udløst af et
    admin-reset) må aldrig efterlade brugeren som om skiftet var tvunget."""
    second, body = await _register("voluntarychange172")
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})

    changed = await second.post(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "myChosenPassword1"},
    )
    assert changed.status_code == 204

    me = await second.get("/api/users/me")
    assert me.json()["must_change_password"] is False
    await second.aclose()
