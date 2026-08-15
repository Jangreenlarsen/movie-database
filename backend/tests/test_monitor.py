from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin5", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/system/monitor")
        assert response.status_code == 403


async def test_health_returns_metrics_and_service_statuses(client):
    response = await client.get("/api/system/monitor")
    assert response.status_code == 200
    data = response.json()

    assert data["mongo_ok"] is True
    # CPU/RAM/disk virker via psutil på enhver platform (også test-maskinen,
    # som ikke er Linux) — kun tjeneste-status/genstart er Linux-only.
    assert isinstance(data["cpu_percent"], (int, float))
    assert isinstance(data["memory_percent"], (int, float))
    assert isinstance(data["disk_percent"], (int, float))
    assert data["uptime_seconds"] > 0

    service_names = [s["name"] for s in data["services"]]
    assert service_names == ["mongod", "caddy", "moviedb-backend"]


async def test_restart_service_is_logged_when_supported(client, monkeypatch):
    from app.services import monitor_service

    calls = []
    # `app.api.monitor` gør `from app.services import monitor_service` og
    # kalder `monitor_service.restart_service()` — samme modul-objekt som
    # importeres her, så en patch på det rammer routerens kald også.
    monkeypatch.setattr(monitor_service, "restart_service", lambda: calls.append("restarted"))

    response = await client.post("/api/system/monitor/restart-service")
    assert response.status_code == 202
    assert calls == ["restarted"]

    log = await client.get("/api/audit-log")
    actions = [e["action"] for e in log.json()["entries"]]
    assert "system.service_restarted" in actions


async def test_restart_service_returns_501_outside_linux(client):
    # Selve test-maskinen er ikke Linux — ingen monkeypatch nødvendig for at
    # bekræfte det faktiske, u-simulerede fallback-udfald.
    response = await client.post("/api/system/monitor/restart-service")
    assert response.status_code == 501


async def test_reboot_requires_correct_password(client):
    response = await client.post("/api/system/monitor/reboot", json={"current_password": "wrong"})
    assert response.status_code == 401


async def test_reboot_with_correct_password_returns_501_outside_linux(client):
    response = await client.post(
        "/api/system/monitor/reboot", json={"current_password": "testpassword123"}
    )
    # Password-tjekket bestod (ellers 401) — fallback til 501 fordi
    # test-maskinen ikke er Linux, ligesom restart-service ovenfor.
    assert response.status_code == 501


async def test_reboot_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin6", "password": "testpassword123"}
        )
        response = await standard_client.post(
            "/api/system/monitor/reboot", json={"current_password": "testpassword123"}
        )
        assert response.status_code == 403
