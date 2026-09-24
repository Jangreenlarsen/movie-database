"""BUGS.md #106 — værn mod gættede adgangskoder på det offentlige login."""

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import login_throttle


async def _anon():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register(username="gaetvaern", password="rigtigtkodeord123"):
    async with await _anon() as anon:
        response = await anon.post(
            "/api/auth/register", json={"username": username, "password": password}
        )
        assert response.status_code == 201, response.text
    return username, password


async def _login(username, password):
    async with await _anon() as anon:
        return await anon.post("/api/auth/login", json={"username": username, "password": password})


async def test_locks_after_max_failures_and_rejects_even_the_right_password(client):
    username, password = await _register()
    for _ in range(login_throttle.MAX_FAILURES):
        assert (await _login(username, "forkert")).status_code == 401

    blocked = await _login(username, "forkert")
    assert blocked.status_code == 429
    assert "Prøv igen om" in blocked.json()["detail"]
    assert int(blocked.headers["Retry-After"]) > 0

    # Også det rigtige kodeord afvises under låsen — ellers kunne en angriber
    # se hvornår et gæt rammer.
    assert (await _login(username, password)).status_code == 429


async def test_lock_lifts_when_the_window_has_passed(client, monkeypatch):
    username, password = await _register()
    now = [1000.0]
    monkeypatch.setattr(login_throttle, "_now", lambda: now[0])
    for _ in range(login_throttle.MAX_FAILURES):
        await _login(username, "forkert")
    assert (await _login(username, password)).status_code == 429

    now[0] += login_throttle.WINDOW_SECONDS + 1
    assert (await _login(username, password)).status_code == 200


async def test_successful_login_resets_the_count(client):
    username, password = await _register()
    for _ in range(login_throttle.MAX_FAILURES - 1):
        await _login(username, "forkert")
    assert (await _login(username, password)).status_code == 200
    # Tælleren er nulstillet: endnu fire forkerte må godt gå igennem som 401.
    for _ in range(login_throttle.MAX_FAILURES - 1):
        assert (await _login(username, "forkert")).status_code == 401


async def test_lock_is_per_username_and_case_insensitive(client):
    victim, _ = await _register("offer")
    other, other_password = await _register("anden")
    for _ in range(login_throttle.MAX_FAILURES):
        await _login("OFFER", "forkert")
    assert (await _login(victim, "forkert")).status_code == 429
    assert (await _login(other, other_password)).status_code == 200


async def test_unknown_usernames_are_throttled_the_same_way(client):
    for _ in range(login_throttle.MAX_FAILURES):
        assert (await _login("findesikke", "x")).status_code == 401
    assert (await _login("findesikke", "x")).status_code == 429


def test_tracked_usernames_are_capped(monkeypatch):
    monkeypatch.setattr(login_throttle, "_MAX_TRACKED", 3)
    for name in ("a", "b", "c", "d", "e"):
        login_throttle.record_failure(name)
    assert len(login_throttle._failures) <= 3
