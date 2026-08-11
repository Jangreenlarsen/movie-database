async def test_feature_list_returns_overview_rows_newest_first(client):
    """Feature #115 — endpoint parser FEATURES.md's oversigts-tabel og
    returnerer den nyeste-først."""
    response = await client.get("/api/system/feature-list")
    assert response.status_code == 200
    items = response.json()
    assert len(items) > 0

    numbers = [item["number"] for item in items]
    # Nyeste (højeste nummer) først.
    assert numbers == sorted(numbers, reverse=True)
    # Oversigts-tabellen har unikke numre; dubletter ville betyde at detalje-
    # tabellen (samme rækkeformat) fejlagtigt blev parset med.
    assert len(numbers) == len(set(numbers))

    # Hver række har de fire offentlige felter — og kun dem.
    sample = items[0]
    assert set(sample.keys()) == {"number", "name", "status", "version"}


async def test_feature_list_includes_a_known_feature(client):
    response = await client.get("/api/system/feature-list")
    items = {item["number"]: item for item in response.json()}
    # #114 (bestillingsstatus) er netop tilføjet og markeret done.
    assert 114 in items
    assert items[114]["status"] == "done"


async def test_feature_list_requires_authentication():
    """Åben for enhver rolle, men ikke helt uden login (get_current_user)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as anon:
        response = await anon.get("/api/system/feature-list")
    assert response.status_code == 401
