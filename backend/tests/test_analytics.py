"""Feature #125 — besøgs-statistik."""

from app.models.analytics import VisitCreate
from app.services import analytics_service


async def test_record_page_visit_is_attributed_to_the_logged_in_user(client):
    r = await client.post("/api/analytics/visit", json={"page": "library"})
    assert r.status_code == 204

    summary = await client.get("/api/analytics/summary")
    assert summary.status_code == 200
    data = summary.json()
    assert data["total_visits"] == 1
    assert data["visits_today"] == 1
    assert data["unique_users"] == 1
    assert data["guest_visits"] == 0
    assert {"name": "library", "count": 1} in data["per_page"]
    assert {"name": "testuser", "count": 1} in data["per_user"]


async def test_title_visit_shows_up_in_top_titles(client):
    await client.post(
        "/api/analytics/visit",
        json={"page": "title", "kind": "title", "resource_kind": "movie", "resource_id": "abc", "title": "Dune"},
    )
    data = (await client.get("/api/analytics/summary")).json()
    assert {"name": "Dune", "count": 1} in data["top_titles"]
    # Et titel-besøg tælles ikke som en side.
    assert data["per_page"] == []


async def test_anonymous_visit_counts_as_guest(client, db):
    # /bio-siden poster uden login → username None. Verificeret på service-
    # niveau, da den indloggede test-klient altid bærer sin cookie.
    await analytics_service.record_visit(db, VisitCreate(page="bio"), None)
    data = (await client.get("/api/analytics/summary")).json()
    assert data["guest_visits"] == 1
    assert data["unique_users"] == 0
    assert {"name": analytics_service.GUEST_SENTINEL, "count": 1} in data["per_user"]


async def test_per_day_series_is_a_continuous_14_day_window(client):
    await client.post("/api/analytics/visit", json={"page": "stats"})
    data = (await client.get("/api/analytics/summary")).json()
    assert len(data["per_day"]) == analytics_service.PER_DAY_WINDOW
    # Sidste dag i serien er i dag og bærer besøget.
    assert data["per_day"][-1]["count"] == 1
    # De foregående dage er nul (kontinuerlig serie med 0-dage).
    assert all(entry["count"] == 0 for entry in data["per_day"][:-1])


async def test_unknown_kind_degrades_to_page(client):
    r = await client.post("/api/analytics/visit", json={"page": "library", "kind": "bogus"})
    assert r.status_code == 204
    data = (await client.get("/api/analytics/summary")).json()
    assert {"name": "library", "count": 1} in data["per_page"]


async def test_summary_requires_authentication(raw_client):
    r = await raw_client.get("/api/analytics/summary")
    assert r.status_code == 401


async def test_recording_a_visit_needs_no_login(raw_client):
    # Det offentlige /bio-besøg må poste uden en session.
    r = await raw_client.post("/api/analytics/visit", json={"page": "bio"})
    assert r.status_code == 204
