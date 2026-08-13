"""Feature #140 — fuldt navn ved registrering, synligt for admin."""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _fresh_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_register_stores_full_name_and_admin_can_see_it(client):
    # `client` er admin (testuser). Opret en ny bruger MED fuldt navn.
    member = await _fresh_client()
    resp = await member.post(
        "/api/auth/register",
        json={"username": "newguy", "password": "testpassword123", "full_name": "Anders And"},
    )
    assert resp.status_code in (200, 201)
    assert resp.json()["full_name"] == "Anders And"

    # Admin ser navnet i bruger-listen (så man ved hvem der beder om adgang).
    users = (await client.get("/api/users")).json()
    newguy = next(u for u in users if u["username"] == "newguy")
    assert newguy["full_name"] == "Anders And"
    await member.aclose()


async def test_register_without_full_name_is_allowed_and_null(client):
    """Backend holder feltet valgfrit (formularen håndhæver det), så den
    eksisterende API-kontrakt/testsuite ikke brydes — udeladt → None."""
    member = await _fresh_client()
    resp = await member.post(
        "/api/auth/register", json={"username": "noname", "password": "testpassword123"}
    )
    assert resp.status_code in (200, 201)
    assert resp.json()["full_name"] is None
    await member.aclose()


async def test_blank_full_name_is_normalized_to_null(client):
    member = await _fresh_client()
    resp = await member.post(
        "/api/auth/register",
        json={"username": "blankname", "password": "testpassword123", "full_name": "   "},
    )
    assert resp.status_code in (200, 201)
    assert resp.json()["full_name"] is None
    await member.aclose()
