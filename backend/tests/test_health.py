from app.core.version_info import VERSION_INFO


async def test_health_reports_current_version(raw_client):
    response = await raw_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == VERSION_INFO["version"]
    assert data["build"] == VERSION_INFO["build"]
