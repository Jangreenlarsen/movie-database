from httpx import ASGITransport, AsyncClient

from app.core.errors import DeployScriptNotFoundError
from app.main import app
from app.services import deploy_service


async def test_deploy_requires_admin(client, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy_service, "trigger_deploy", lambda: calls.append(1))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        response = await standard_client.post("/api/system/deploy")
        assert response.status_code == 403
    assert calls == []


async def test_deploy_triggers_for_admin(client, monkeypatch):
    """The `client` fixture's user is always admin (first registered user)."""
    calls = []
    monkeypatch.setattr(deploy_service, "trigger_deploy", lambda: calls.append(1))

    response = await client.post("/api/system/deploy")
    assert response.status_code == 202
    assert response.json() == {"status": "started"}
    assert calls == [1]


async def test_deploy_returns_500_when_script_missing(client, monkeypatch):
    def fake_trigger():
        raise DeployScriptNotFoundError("/opt/moviedb-deploy.sh")

    monkeypatch.setattr(deploy_service, "trigger_deploy", fake_trigger)

    response = await client.post("/api/system/deploy")
    assert response.status_code == 500
    assert "opt/moviedb-deploy.sh" in response.json()["detail"]


async def test_trigger_deploy_raises_when_script_missing(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "deploy_script_path", str(tmp_path / "does-not-exist.sh"))
    monkeypatch.setattr(settings, "deploy_log_path", str(tmp_path / "deploy.log"))

    try:
        deploy_service.trigger_deploy()
        assert False, "expected DeployScriptNotFoundError"
    except DeployScriptNotFoundError:
        pass


async def test_trigger_deploy_launches_detached_process(tmp_path, monkeypatch):
    script = tmp_path / "deploy.sh"
    script.write_text("#!/bin/bash\necho hi\n")
    log_path = tmp_path / "deploy.log"

    from app.core.config import settings

    monkeypatch.setattr(settings, "deploy_script_path", str(script))
    monkeypatch.setattr(settings, "deploy_log_path", str(log_path))

    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(deploy_service.subprocess, "Popen", FakePopen)

    deploy_service.trigger_deploy()

    assert captured["args"] == [str(script)]
    assert captured["kwargs"]["start_new_session"] is True


# BUGS.md #36 — deploy-status polling (skelner "intet nyt at hente" fra en reel fejl).


async def test_deploy_status_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin2", "password": "testpassword123"}
        )
        response = await standard_client.get("/api/system/deploy/status")
        assert response.status_code == 403


async def test_deploy_status_returns_unknown_when_file_missing(client, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "deploy_status_path", str(tmp_path / "does-not-exist.json"))

    response = await client.get("/api/system/deploy/status")
    assert response.status_code == 200
    assert response.json() == {"outcome": "unknown"}


async def test_deploy_status_reads_written_outcome(client, tmp_path, monkeypatch):
    from app.core.config import settings

    status_path = tmp_path / ".deploy-status"
    status_path.write_text('{"outcome":"up-to-date","commit":"abc123","at":"2026-08-03T19:47:12Z"}')
    monkeypatch.setattr(settings, "deploy_status_path", str(status_path))

    response = await client.get("/api/system/deploy/status")
    assert response.status_code == 200
    assert response.json() == {"outcome": "up-to-date", "commit": "abc123", "at": "2026-08-03T19:47:12Z"}


async def test_get_deploy_status_handles_corrupt_file(tmp_path, monkeypatch):
    from app.core.config import settings

    status_path = tmp_path / ".deploy-status"
    status_path.write_text("not valid json")
    monkeypatch.setattr(settings, "deploy_status_path", str(status_path))

    assert deploy_service.get_deploy_status() == {"outcome": "unknown"}
