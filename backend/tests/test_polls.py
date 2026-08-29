"""Feature #162 (Jan, 2026-08-15: "Kunne man lave en afstemning side hvor
man kunne stemme på nogen udvalgte film hvor den/dem så blev vist på en
given dato?"). Scope afklaret 2026-08-29 via fire spørgsmål: én stemme pr.
bruger (ombestembelig), stemmetal synlige undervejs, kun admin opretter,
uafgjort løses ved at admin vælger manuelt blandt topscorerne."""

from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.integrations import email_client
from app.main import app


async def _member(admin_client, name, role="guest"):
    transport = ASGITransport(app=app)
    member = AsyncClient(transport=transport, base_url="http://test")
    register = await member.post(
        "/api/auth/register", json={"username": name, "password": "testpassword123"}
    )
    await admin_client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})
    await admin_client.patch(f"/api/users/{register.json()['id']}/email", json={"email": f"{name}@example.com"})
    if role != "guest":
        await admin_client.patch(f"/api/users/{register.json()['id']}/role", json={"role": role})
    return member


async def _create_movie(client, title):
    created = await client.post(
        "/api/movies", json={"title": title, "media_type": "Fysisk", "format": "F-DVD"}
    )
    return created.json()["id"]


async def _create_poll(client, candidate_movie_ids, title=None):
    payload = {
        "candidates": [{"media_kind": "movie", "movie_id": mid} for mid in candidate_movie_ids]
    }
    if title:
        payload["title"] = title
    response = await client.post("/api/polls", json=payload)
    return response


def _configure_resend(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")


def _capture_email(monkeypatch):
    calls = []

    async def fake_send_email(to, subject, text, html=None):
        calls.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    monkeypatch.setattr(email_client, "send_email", fake_send_email)
    return calls


async def test_admin_can_create_a_poll(client):
    a = await _create_movie(client, "Kandidat A")
    b = await _create_movie(client, "Kandidat B")

    response = await _create_poll(client, [a, b])
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["title"] == "Kandidat A"
    assert body["candidates"][0]["vote_count"] == 0
    assert body["total_votes"] == 0
    assert body["my_vote"] is None


async def test_nonadmin_cannot_create_a_poll(client):
    guest = await _member(client, "poll_guest_create")
    a = await _create_movie(client, "Kandidat C")
    b = await _create_movie(client, "Kandidat D")

    response = await _create_poll(guest, [a, b])
    assert response.status_code == 403
    await guest.aclose()


async def test_poll_requires_at_least_two_candidates(client):
    a = await _create_movie(client, "Kun En")
    response = await _create_poll(client, [a])
    assert response.status_code == 422


async def test_poll_rejects_duplicate_candidates(client):
    a = await _create_movie(client, "Samme Film")
    response = await _create_poll(client, [a, a])
    assert response.status_code == 422


async def test_guest_can_vote(client):
    """Feature #72-parallel — stemme er den ene skrive-handling gæster har
    adgang til, samme princip som at anmode om en forvisning."""
    guest = await _member(client, "poll_guest_vote")
    a = await _create_movie(client, "Stem A")
    b = await _create_movie(client, "Stem B")
    poll = (await _create_poll(client, [a, b])).json()

    response = await guest.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["candidates"][0]["vote_count"] == 1
    assert body["total_votes"] == 1
    assert body["my_vote"] == 0
    await guest.aclose()


async def test_changing_your_vote_does_not_duplicate_it(client):
    guest = await _member(client, "poll_guest_change")
    a = await _create_movie(client, "Skift A")
    b = await _create_movie(client, "Skift B")
    poll = (await _create_poll(client, [a, b])).json()

    await guest.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    response = await guest.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 1})

    body = response.json()
    assert body["total_votes"] == 1
    assert body["candidates"][0]["vote_count"] == 0
    assert body["candidates"][1]["vote_count"] == 1
    assert body["my_vote"] == 1
    await guest.aclose()


async def test_vote_rejects_an_invalid_candidate_index(client):
    a = await _create_movie(client, "Ugyldig A")
    b = await _create_movie(client, "Ugyldig B")
    poll = (await _create_poll(client, [a, b])).json()

    response = await client.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 5})
    assert response.status_code == 422


async def test_vote_is_rejected_once_the_poll_is_closed(client):
    a = await _create_movie(client, "Lukket A")
    b = await _create_movie(client, "Lukket B")
    poll = (await _create_poll(client, [a, b])).json()
    await client.post(f"/api/polls/{poll['id']}/close")

    response = await client.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    assert response.status_code == 409


async def test_nonadmin_cannot_close_a_poll(client):
    guest = await _member(client, "poll_guest_close")
    a = await _create_movie(client, "Ej Luk A")
    b = await _create_movie(client, "Ej Luk B")
    poll = (await _create_poll(client, [a, b])).json()

    response = await guest.post(f"/api/polls/{poll['id']}/close")
    assert response.status_code == 403
    await guest.aclose()


async def test_closing_a_poll_computes_a_single_winner(client):
    voter1 = await _member(client, "poll_winner_v1")
    voter2 = await _member(client, "poll_winner_v2")
    a = await _create_movie(client, "Vinder A")
    b = await _create_movie(client, "Vinder B")
    poll = (await _create_poll(client, [a, b])).json()

    await voter1.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    await voter2.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})

    response = await client.post(f"/api/polls/{poll['id']}/close")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    assert body["winner_indices"] == [0]
    await voter1.aclose()
    await voter2.aclose()


async def test_closing_a_tied_poll_lists_all_top_candidates(client):
    voter1 = await _member(client, "poll_tie_v1")
    voter2 = await _member(client, "poll_tie_v2")
    a = await _create_movie(client, "Uafgjort A")
    b = await _create_movie(client, "Uafgjort B")
    poll = (await _create_poll(client, [a, b])).json()

    await voter1.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    await voter2.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 1})

    response = await client.post(f"/api/polls/{poll['id']}/close")
    body = response.json()
    assert sorted(body["winner_indices"]) == [0, 1]
    await voter1.aclose()
    await voter2.aclose()


async def test_closing_twice_is_rejected(client):
    a = await _create_movie(client, "Dobbelt A")
    b = await _create_movie(client, "Dobbelt B")
    poll = (await _create_poll(client, [a, b])).json()
    await client.post(f"/api/polls/{poll['id']}/close")

    response = await client.post(f"/api/polls/{poll['id']}/close")
    assert response.status_code == 409


async def test_closing_a_poll_notifies_every_voter(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    voter = await _member(client, "poll_notify_close")
    a = await _create_movie(client, "Besked A")
    b = await _create_movie(client, "Besked B")
    poll = (await _create_poll(client, [a, b])).json()
    await voter.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})

    await client.post(f"/api/polls/{poll['id']}/close")

    inbox = (await voter.get("/api/messages/inbox")).json()
    assert any(m["subject"] == "Afstemningen er afgjort" for m in inbox)
    assert len(calls) == 1
    assert "Besked A" in calls[0]["html"]
    await voter.aclose()


async def test_scheduling_the_winner_marks_the_poll_scheduled_and_notifies_voters(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    voter = await _member(client, "poll_notify_scheduled")
    a = await _create_movie(client, "Planlagt Vinder")
    b = await _create_movie(client, "Planlagt Taber")
    poll = (await _create_poll(client, [a, b])).json()
    await voter.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    await client.post(f"/api/polls/{poll['id']}/close")

    scheduled = await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": a,
            "scheduled_at": "2099-09-01T20:00:00",
            "poll_id": poll["id"],
        },
    )
    assert scheduled.status_code == 201

    poll_after = (await client.get(f"/api/polls/{poll['id']}")).json()
    assert poll_after["status"] == "scheduled"
    assert poll_after["scheduled_screening_id"] == scheduled.json()["id"]

    inbox = (await voter.get("/api/messages/inbox")).json()
    assert any("Planlagt Vinder" in m["body"] for m in inbox)
    assert len(calls) == 2  # closed-notification + scheduled-notification
    await voter.aclose()


async def test_scheduling_with_an_unknown_poll_id_returns_404(client):
    a = await _create_movie(client, "Intet Poll")
    response = await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": a,
            "scheduled_at": "2099-09-01T20:00:00",
            "poll_id": "000000000000000000000000",
        },
    )
    assert response.status_code == 404


async def test_poll_can_be_created_with_a_target_date(client):
    """Feature #208 (Jan: "afstemming skal kunne sættes en dato på til de
    film vi stemmer om til forvisning")."""
    a = await _create_movie(client, "Dato A")
    b = await _create_movie(client, "Dato B")

    response = await client.post(
        "/api/polls",
        json={
            "candidates": [
                {"media_kind": "movie", "movie_id": a},
                {"media_kind": "movie", "movie_id": b},
            ],
            "target_date": "2099-09-05",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["target_date"].startswith("2099-09-05")


async def test_poll_target_date_is_optional(client):
    a = await _create_movie(client, "Ingen Dato A")
    b = await _create_movie(client, "Ingen Dato B")

    response = await _create_poll(client, [a, b])
    assert response.status_code == 201
    assert response.json()["target_date"] is None


async def test_list_polls_can_filter_by_status(client):
    a = await _create_movie(client, "Filter A")
    b = await _create_movie(client, "Filter B")
    open_poll = (await _create_poll(client, [a, b])).json()
    c = await _create_movie(client, "Filter C")
    d = await _create_movie(client, "Filter D")
    closed_poll = (await _create_poll(client, [c, d])).json()
    await client.post(f"/api/polls/{closed_poll['id']}/close")

    open_only = (await client.get("/api/polls?status=open")).json()
    assert [p["id"] for p in open_only] == [open_poll["id"]]

    closed_only = (await client.get("/api/polls?status=closed")).json()
    assert [p["id"] for p in closed_only] == [closed_poll["id"]]
