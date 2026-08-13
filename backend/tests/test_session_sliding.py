"""Feature #148 — 8 timers skydende idle-timeout."""

from app.core.config import settings


async def test_session_lifetime_is_8_hours():
    assert settings.jwt_expire_minutes == 8 * 60


async def test_authenticated_request_refreshes_the_session_cookie(client):
    # En almindelig (ikke-baggrunds) request forlænger sessionen: middleware'n
    # gen-udsteder cookien.
    resp = await client.get("/api/movies")
    assert resp.status_code == 200
    assert resp.cookies.get("access_token")  # ny cookie sat


async def test_background_poll_does_not_refresh_the_cookie(client):
    # Besked-pollen (markeret X-Background-Poll) tæller ikke som aktivitet.
    resp = await client.get(
        "/api/messages/inbox", headers={"X-Background-Poll": "1"}
    )
    assert resp.status_code == 200
    assert resp.cookies.get("access_token") is None


async def test_logout_is_not_revived_by_the_sliding_middleware(client):
    # /api/auth er undtaget, så logouts cookie-sletning ikke gen-udstedes.
    await client.post("/api/auth/logout")
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401
