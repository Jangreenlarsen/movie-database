"""Feature #204 (Jan: "vi skal have lavet en fede svar email til users når
de få svar fra movie portal med billeder og indspirerende tekst") — de
seks admin→bruger-svar-notifikationer (godkendt/afvist/bestilt/flyttet for
ønsker, afvist/planlagt for forvisnings-anmodninger) sender nu en rigere
HTML-udgave af mailen (poster-billede når kendt, en kort "inspirerende"
tagline) ved siden af den uændrede rene tekst. Selve LAYOUTET testes i
test_email_templates.py — her testes kun at hver funktion rent faktisk
bygger og sender et html-argument med det forventede indhold."""

from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.integrations import email_client
from app.main import app

POSTER = "https://image.tmdb.org/t/p/w342/test-poster.jpg"


async def _member(admin_client, name):
    transport = ASGITransport(app=app)
    member = AsyncClient(transport=transport, base_url="http://test")
    register = await member.post(
        "/api/auth/register", json={"username": name, "password": "testpassword123"}
    )
    await admin_client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})
    await admin_client.patch(f"/api/users/{register.json()['id']}/email", json={"email": f"{name}@example.com"})
    return member


def _configure_resend(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")


def _capture_html(monkeypatch):
    calls = []

    async def fake_send_email(to, subject, text, html=None):
        calls.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    monkeypatch.setattr(email_client, "send_email", fake_send_email)
    return calls


async def test_wishlist_approved_email_includes_poster_and_tagline(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_html(monkeypatch)
    member = await _member(client, "approve_html")

    created = await member.post(
        "/api/movies", json={"title": "Godkend Mail", "is_wishlist": True, "poster_url": POSTER}
    )
    resp = await client.patch(
        f"/api/movies/{created.json()['id']}", json={"wishlist_status": "approved"}
    )
    assert resp.status_code == 200

    assert len(calls) == 1
    assert calls[0]["html"] is not None
    assert POSTER in calls[0]["html"]
    assert "Godkend Mail" in calls[0]["html"]
    await member.aclose()


async def test_wishlist_rejected_email_has_no_poster_when_unknown(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_html(monkeypatch)
    member = await _member(client, "reject_html")

    created = await member.post("/api/movies", json={"title": "Afvis Mail", "is_wishlist": True})
    resp = await client.post(
        f"/api/movies/{created.json()['id']}/reject-wish", json={"message": "Findes ikke"}
    )
    assert resp.status_code == 204

    assert len(calls) == 1
    assert calls[0]["html"] is not None
    assert "<img" not in calls[0]["html"]
    assert "Afvis Mail" in calls[0]["html"]
    await member.aclose()


async def test_wishlist_ordered_email_includes_tagline(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_html(monkeypatch)
    member = await _member(client, "order_html")

    created = await member.post("/api/movies", json={"title": "Bestil Mail", "is_wishlist": True})
    resp = await client.patch(
        f"/api/movies/{created.json()['id']}", json={"order_status": "Bestilt ved iMusic"}
    )
    assert resp.status_code == 200

    assert len(calls) == 1
    assert "Bestilt!" in calls[0]["html"]
    assert "Bestil Mail" in calls[0]["html"]
    await member.aclose()


async def test_wishlist_moved_to_library_email_includes_tagline(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_html(monkeypatch)
    member = await _member(client, "move_html")

    created = await member.post("/api/movies", json={"title": "Flyt Mail", "is_wishlist": True})
    resp = await client.patch(
        f"/api/movies/{created.json()['id']}",
        json={"is_wishlist": False, "media_type": "Fysisk", "format": "F-DVD"},
    )
    assert resp.status_code == 200

    assert len(calls) == 1
    assert "hylden" in calls[0]["html"]
    assert "Flyt Mail" in calls[0]["html"]
    await member.aclose()


async def test_screening_request_declined_email_includes_poster(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_html(monkeypatch)
    member = await _member(client, "declined_html")

    movie = await client.post(
        "/api/movies", json={"title": "Afvist Visning Mail", "media_type": "Fysisk", "format": "F-DVD", "poster_url": POSTER}
    )
    created = await member.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie.json()["id"], "preferred_at": "2099-09-01T20:00:00"},
    )
    request_id = created.json()["id"]

    resp = await client.patch(f"/api/screening-requests/{request_id}", json={"status": "declined"})
    assert resp.status_code == 200

    assert len(calls) == 1
    assert calls[0]["html"] is not None
    assert POSTER in calls[0]["html"]
    assert "Afvist Visning Mail" in calls[0]["html"]
    await member.aclose()


async def test_screening_request_scheduled_email_includes_poster(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_html(monkeypatch)
    member = await _member(client, "scheduled_html")

    movie = await client.post(
        "/api/movies", json={"title": "Planlagt Visning Mail", "media_type": "Fysisk", "format": "F-DVD", "poster_url": POSTER}
    )
    created = await member.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie.json()["id"], "preferred_at": "2099-09-01T20:00:00"},
    )
    request_id = created.json()["id"]

    resp = await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie.json()["id"],
            "scheduled_at": "2099-09-01T20:00:00",
            "request_id": request_id,
        },
    )
    assert resp.status_code == 201

    assert len(calls) == 1
    assert calls[0]["html"] is not None
    assert POSTER in calls[0]["html"]
    assert "Planlagt Visning Mail" in calls[0]["html"]
    await member.aclose()


async def test_admin_broadcast_message_has_no_html(client, monkeypatch):
    """Kun de seks svar-funktioner bygger en HTML-mail — en almindelig
    admin-komponeret besked (fri tekst, ingen film/tv-kontekst) forbliver
    ren tekst, som før feature #204."""
    _configure_resend(monkeypatch)
    calls = _capture_html(monkeypatch)
    member = await _member(client, "broadcast_html")

    resp = await client.post("/api/messages", json={"subject": "Emne", "body": "Krop"})
    assert resp.status_code == 201

    assert len(calls) == 1
    assert calls[0]["html"] is None
    await member.aclose()
