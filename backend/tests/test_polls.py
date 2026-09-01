"""Feature #162 (Jan, 2026-08-15: "Kunne man lave en afstemning side hvor
man kunne stemme på nogen udvalgte film hvor den/dem så blev vist på en
given dato?"). Scope afklaret 2026-08-29 via fire spørgsmål: én stemme pr.
bruger (ombestembelig), stemmetal synlige undervejs, kun admin opretter,
uafgjort løses ved at admin vælger manuelt blandt topscorerne."""

from datetime import datetime, timedelta, timezone

from bson import ObjectId
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


async def _create_poll(client, candidate_movie_ids, title=None, voting_deadline=None):
    payload = {
        "candidates": [{"media_kind": "movie", "movie_id": mid} for mid in candidate_movie_ids]
    }
    if title:
        payload["title"] = title
    if voting_deadline:
        payload["voting_deadline"] = voting_deadline
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


async def test_nonadmin_creates_a_pending_poll_not_an_open_one(client):
    """Feature #213 (Jan: "guest kan opret en afsteming ... men det er en
    adm som skal godkende at afsteming skal gøre global for alle") —
    erstatter den tidligere test_nonadmin_cannot_create_a_poll: oprettelse
    er nu åben for enhver rolle, men resultatet starter 'pending', ikke
    'open'."""
    guest = await _member(client, "poll_guest_create")
    a = await _create_movie(client, "Kandidat C")
    b = await _create_movie(client, "Kandidat D")

    response = await _create_poll(guest, [a, b])
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
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


async def test_scheduled_poll_still_shows_while_the_premiere_is_in_the_future(client):
    a = await _create_movie(client, "Fremtid A")
    b = await _create_movie(client, "Fremtid B")
    poll = (await _create_poll(client, [a, b])).json()
    await client.post(f"/api/polls/{poll['id']}/close")
    await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": a,
            "scheduled_at": "2099-09-01T20:00:00",
            "poll_id": poll["id"],
        },
    )

    polls = (await client.get("/api/polls")).json()
    assert poll["id"] in [p["id"] for p in polls]


async def test_scheduled_poll_disappears_once_the_premiere_has_passed(client):
    """Jan: "de skal forsvinder efter film har haft premiære"."""
    a = await _create_movie(client, "Fortid A")
    b = await _create_movie(client, "Fortid B")
    poll = (await _create_poll(client, [a, b])).json()
    await client.post(f"/api/polls/{poll['id']}/close")
    await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": a,
            "scheduled_at": "2020-01-01T20:00:00",
            "poll_id": poll["id"],
        },
    )

    polls = (await client.get("/api/polls")).json()
    assert poll["id"] not in [p["id"] for p in polls]


async def test_a_premiered_poll_can_still_be_fetched_directly_by_id(client):
    a = await _create_movie(client, "Direkte A")
    b = await _create_movie(client, "Direkte B")
    poll = (await _create_poll(client, [a, b])).json()
    await client.post(f"/api/polls/{poll['id']}/close")
    await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": a,
            "scheduled_at": "2020-01-01T20:00:00",
            "poll_id": poll["id"],
        },
    )

    response = await client.get(f"/api/polls/{poll['id']}")
    assert response.status_code == 200


async def test_admin_can_delete_a_poll_at_any_time(client):
    """Jan: "eller adm vælger at de skal forsvinde"."""
    a = await _create_movie(client, "Slet A")
    b = await _create_movie(client, "Slet B")
    poll = (await _create_poll(client, [a, b])).json()

    response = await client.delete(f"/api/polls/{poll['id']}")
    assert response.status_code == 204

    polls = (await client.get("/api/polls")).json()
    assert poll["id"] not in [p["id"] for p in polls]


async def test_deleting_a_scheduled_poll_does_not_remove_its_screening(client):
    a = await _create_movie(client, "Behold A")
    b = await _create_movie(client, "Behold B")
    poll = (await _create_poll(client, [a, b])).json()
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

    await client.delete(f"/api/polls/{poll['id']}")

    screenings = (await client.get("/api/screenings")).json()
    assert scheduled.json()["id"] in [s["id"] for s in screenings]


async def test_nonadmin_cannot_delete_a_poll(client):
    guest = await _member(client, "poll_guest_delete")
    a = await _create_movie(client, "Ej Slet A")
    b = await _create_movie(client, "Ej Slet B")
    poll = (await _create_poll(client, [a, b])).json()

    response = await guest.delete(f"/api/polls/{poll['id']}")
    assert response.status_code == 403
    await guest.aclose()


async def test_deleting_an_unknown_poll_returns_404(client):
    response = await client.delete("/api/polls/000000000000000000000000")
    assert response.status_code == 404


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


# Feature #213 (Jan: "guest kan opret en afsteming med x antal film til
# afsteming men det er en adm som skal godkende at afsteming skal gøre
# global for alle efter følgende og det er også adm som kan tilret listen
# som en guest vil laveafsteming på").


async def test_pending_poll_is_visible_to_its_creator(client):
    guest = await _member(client, "poll_pending_own")
    a = await _create_movie(client, "Eget Forslag A")
    b = await _create_movie(client, "Eget Forslag B")
    poll = (await _create_poll(guest, [a, b])).json()

    own_view = (await guest.get("/api/polls")).json()
    assert poll["id"] in [p["id"] for p in own_view]
    await guest.aclose()


async def test_pending_poll_is_visible_to_admin(client):
    guest = await _member(client, "poll_pending_admin_view")
    a = await _create_movie(client, "Admin Ser A")
    b = await _create_movie(client, "Admin Ser B")
    poll = (await _create_poll(guest, [a, b])).json()

    admin_view = (await client.get("/api/polls")).json()
    assert poll["id"] in [p["id"] for p in admin_view]
    await guest.aclose()


async def test_pending_poll_is_hidden_from_other_nonadmins(client):
    creator = await _member(client, "poll_pending_creator")
    other = await _member(client, "poll_pending_other")
    a = await _create_movie(client, "Skjult A")
    b = await _create_movie(client, "Skjult B")
    poll = (await _create_poll(creator, [a, b])).json()

    other_view = (await other.get("/api/polls")).json()
    assert poll["id"] not in [p["id"] for p in other_view]

    direct_fetch = await other.get(f"/api/polls/{poll['id']}")
    assert direct_fetch.status_code == 404
    await creator.aclose()
    await other.aclose()


async def test_cannot_vote_on_a_pending_poll(client):
    guest = await _member(client, "poll_pending_vote")
    a = await _create_movie(client, "Ej Stemme A")
    b = await _create_movie(client, "Ej Stemme B")
    poll = (await _create_poll(guest, [a, b])).json()

    response = await guest.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    assert response.status_code == 409
    await guest.aclose()


async def test_admin_can_approve_a_pending_poll(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    guest = await _member(client, "poll_approve")
    a = await _create_movie(client, "Godkend A")
    b = await _create_movie(client, "Godkend B")
    poll = (await _create_poll(guest, [a, b])).json()

    response = await client.post(f"/api/polls/{poll['id']}/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "open"

    # Nu global — synlig for en helt tredje bruger, og stemmebar.
    other = await _member(client, "poll_approve_voter")
    other_view = (await other.get("/api/polls")).json()
    assert poll["id"] in [p["id"] for p in other_view]
    vote = await other.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    assert vote.status_code == 200

    inbox = (await guest.get("/api/messages/inbox")).json()
    assert any(m["subject"] == "Din afstemning er godkendt" for m in inbox)
    assert len(calls) == 1
    await guest.aclose()
    await other.aclose()


async def test_nonadmin_cannot_approve_a_poll(client):
    guest = await _member(client, "poll_approve_denied")
    a = await _create_movie(client, "Ej Godkend A")
    b = await _create_movie(client, "Ej Godkend B")
    poll = (await _create_poll(guest, [a, b])).json()

    response = await guest.post(f"/api/polls/{poll['id']}/approve")
    assert response.status_code == 403
    await guest.aclose()


async def test_approving_an_already_open_poll_is_rejected(client):
    a = await _create_movie(client, "Allerede Åben A")
    b = await _create_movie(client, "Allerede Åben B")
    poll = (await _create_poll(client, [a, b])).json()  # admin-oprettet, starter 'open'

    response = await client.post(f"/api/polls/{poll['id']}/approve")
    assert response.status_code == 409


async def test_admin_can_edit_candidates_on_a_pending_poll(client):
    guest = await _member(client, "poll_edit_candidates")
    a = await _create_movie(client, "Byt Ud A")
    b = await _create_movie(client, "Byt Ud B")
    c = await _create_movie(client, "Ny Kandidat C")
    poll = (await _create_poll(guest, [a, b])).json()

    response = await client.patch(
        f"/api/polls/{poll['id']}/candidates",
        json={
            "candidates": [
                {"media_kind": "movie", "movie_id": a},
                {"media_kind": "movie", "movie_id": c},
            ]
        },
    )
    assert response.status_code == 200
    titles = {c["title"] for c in response.json()["candidates"]}
    assert titles == {"Byt Ud A", "Ny Kandidat C"}
    await guest.aclose()


async def test_nonadmin_cannot_edit_poll_candidates(client):
    guest = await _member(client, "poll_edit_denied")
    a = await _create_movie(client, "Ej Redigér A")
    b = await _create_movie(client, "Ej Redigér B")
    poll = (await _create_poll(guest, [a, b])).json()

    response = await guest.patch(
        f"/api/polls/{poll['id']}/candidates",
        json={"candidates": [{"media_kind": "movie", "movie_id": a}, {"media_kind": "movie", "movie_id": b}]},
    )
    assert response.status_code == 403
    await guest.aclose()


async def test_editing_candidates_on_an_open_poll_is_rejected(client):
    a = await _create_movie(client, "Åben Rediger A")
    b = await _create_movie(client, "Åben Rediger B")
    poll = (await _create_poll(client, [a, b])).json()  # admin-oprettet, allerede 'open'

    response = await client.patch(
        f"/api/polls/{poll['id']}/candidates",
        json={"candidates": [{"media_kind": "movie", "movie_id": a}, {"media_kind": "movie", "movie_id": b}]},
    )
    assert response.status_code == 409


async def test_editing_candidates_still_requires_at_least_two(client):
    guest = await _member(client, "poll_edit_too_few")
    a = await _create_movie(client, "For Få A")
    b = await _create_movie(client, "For Få B")
    poll = (await _create_poll(guest, [a, b])).json()

    response = await client.patch(
        f"/api/polls/{poll['id']}/candidates",
        json={"candidates": [{"media_kind": "movie", "movie_id": a}]},
    )
    assert response.status_code == 422
    await guest.aclose()


async def test_rejecting_a_pending_poll_notifies_the_creator(client, monkeypatch):
    """Admin bruger den eksisterende DELETE til at afvise et forslag — der
    er ikke bedt om en separat afvis-handling (se poll_service.delete_poll's
    docstring)."""
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    guest = await _member(client, "poll_reject")
    a = await _create_movie(client, "Afvis A")
    b = await _create_movie(client, "Afvis B")
    poll = (await _create_poll(guest, [a, b])).json()

    response = await client.delete(f"/api/polls/{poll['id']}")
    assert response.status_code == 204

    inbox = (await guest.get("/api/messages/inbox")).json()
    assert any(m["subject"] == "Om dit afstemnings-forslag" for m in inbox)
    assert len(calls) == 1
    await guest.aclose()


async def test_creating_a_pending_poll_notifies_admins(client):
    """Samme in-app-only afprøvning som de øvrige notify_admins_new_*-
    tests (fx test_screening_notifications.py) — admin-fixturen har ingen
    e-mail sat, så kun indbakke-beskeden tjekkes her."""
    guest = await _member(client, "poll_notify_admin")
    a = await _create_movie(client, "Meld A")
    b = await _create_movie(client, "Meld B")

    await _create_poll(guest, [a, b])

    admin_inbox = (await client.get("/api/messages/inbox")).json()
    assert any(m["subject"] == "Nyt afstemnings-forslag afventer godkendelse" for m in admin_inbox)
    await guest.aclose()


async def test_deleting_an_already_decided_poll_does_not_notify_anyone(client, monkeypatch):
    """Kun en fjernet 'pending' afstemning tolkes som en afvisning, og kun
    en fjernet ENDNU ÅBEN afstemning udløser feature #216's aflysnings-
    besked (se testene nedenfor) — en allerede afgjort (lukket) afstemning
    der ryddes op er ikke en overraskelse for nogen (alle involverede har
    allerede set udfaldet, via notify_poll_closed ved selve lukningen)."""
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    voter = await _member(client, "poll_decided_cleanup")
    a = await _create_movie(client, "Oprydning A")
    b = await _create_movie(client, "Oprydning B")
    poll = (await _create_poll(client, [a, b])).json()  # admin-oprettet, 'open'
    await voter.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    await client.post(f"/api/polls/{poll['id']}/close")
    calls.clear()  # selve lukningen sender allerede sin egen "afgjort"-besked

    await client.delete(f"/api/polls/{poll['id']}")

    assert len(calls) == 0
    await voter.aclose()


# Feature #216 (Jan: "når man sletter en afstemning så få users ikke notet
# om det, lan en besked som forklar at afstemings filmen er desvære aflyst
# af biograffens bestyrelse destående af de 7 små dværge, eller noget andet
# sjovt lave eventuelt en rotation med 5 forskeling besked typer med samme
# mening").


async def test_deleting_an_open_poll_notifies_every_voter(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    voter1 = await _member(client, "poll_cancel_v1")
    voter2 = await _member(client, "poll_cancel_v2")
    a = await _create_movie(client, "Aflyst A")
    b = await _create_movie(client, "Aflyst B")
    poll = (await _create_poll(client, [a, b])).json()  # admin-oprettet, 'open'
    await voter1.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    await voter2.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 1})

    response = await client.delete(f"/api/polls/{poll['id']}")
    assert response.status_code == 204

    inbox1 = (await voter1.get("/api/messages/inbox")).json()
    inbox2 = (await voter2.get("/api/messages/inbox")).json()
    assert any(m["subject"] == "Afstemningen er aflyst" for m in inbox1)
    assert any(m["subject"] == "Afstemningen er aflyst" for m in inbox2)
    assert len(calls) == 2
    await voter1.aclose()
    await voter2.aclose()


async def test_cancelled_poll_message_is_one_of_the_five_rotating_variants(client, monkeypatch):
    from app.services.message_service import _POLL_CANCELLED_MESSAGES

    assert len(_POLL_CANCELLED_MESSAGES) == 5
    _configure_resend(monkeypatch)
    _capture_email(monkeypatch)
    voter = await _member(client, "poll_cancel_variant")
    a = await _create_movie(client, "Variant A")
    b = await _create_movie(client, "Variant B")
    poll = (await _create_poll(client, [a, b])).json()
    await voter.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})

    await client.delete(f"/api/polls/{poll['id']}")

    inbox = (await voter.get("/api/messages/inbox")).json()
    message = next(m for m in inbox if m["subject"] == "Afstemningen er aflyst")
    assert message["body"] in _POLL_CANCELLED_MESSAGES
    await voter.aclose()


async def test_deleting_an_open_poll_with_no_votes_notifies_no_one(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    a = await _create_movie(client, "Ingen Stemmer A")
    b = await _create_movie(client, "Ingen Stemmer B")
    poll = (await _create_poll(client, [a, b])).json()  # admin-oprettet, 'open', ingen stemmer

    await client.delete(f"/api/polls/{poll['id']}")

    assert len(calls) == 0


async def test_admin_deleting_an_open_poll_they_voted_on_does_not_notify_themselves(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    a = await _create_movie(client, "Admin Egen A")
    b = await _create_movie(client, "Admin Egen B")
    poll = (await _create_poll(client, [a, b])).json()
    await client.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})

    await client.delete(f"/api/polls/{poll['id']}")

    assert len(calls) == 0


# Feature #215 (Jan: "og så skal vi have en tidsfrest på også") — valgfri
# stemme-frist. PollCreate afviser en frist der allerede ligger i fortiden
# (testet nedenfor), så "allerede udløbet" i de øvrige tests opnås ved
# direkte at rykke en allerede-oprettet afstemnings frist bagud i databasen
# via `db`-fixturet — samme situation som blot at vente til fristen
# passerer, uden at testen selv skal sove.


async def test_creating_a_poll_with_a_past_voting_deadline_is_rejected(client):
    a = await _create_movie(client, "Frist Fortid A")
    b = await _create_movie(client, "Frist Fortid B")

    response = await _create_poll(client, [a, b], voting_deadline="2020-01-01T20:00:00")
    assert response.status_code == 422


async def test_poll_shows_its_voting_deadline_when_set(client):
    a = await _create_movie(client, "Frist Fremtid A")
    b = await _create_movie(client, "Frist Fremtid B")
    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:00")

    response = await _create_poll(client, [a, b], voting_deadline=future)
    assert response.status_code == 201
    assert response.json()["voting_deadline"] is not None


async def test_a_poll_without_a_voting_deadline_never_auto_closes(client):
    a = await _create_movie(client, "Ingen Frist A")
    b = await _create_movie(client, "Ingen Frist B")
    poll = (await _create_poll(client, [a, b])).json()

    polls = (await client.get("/api/polls")).json()
    updated = next(p for p in polls if p["id"] == poll["id"])
    assert updated["status"] == "open"


async def test_open_poll_auto_closes_once_its_voting_deadline_has_passed(client, db):
    a = await _create_movie(client, "Udløbet A")
    b = await _create_movie(client, "Udløbet B")
    poll = (await _create_poll(client, [a, b])).json()  # admin-oprettet, 'open'
    await db["polls"].update_one(
        {"_id": ObjectId(poll["id"])},
        {"$set": {"voting_deadline": datetime(2020, 1, 1, tzinfo=timezone.utc)}},
    )

    polls = (await client.get("/api/polls")).json()
    updated = next(p for p in polls if p["id"] == poll["id"])
    assert updated["status"] == "closed"


async def test_a_single_expired_poll_can_still_be_fetched_directly_by_id(client, db):
    a = await _create_movie(client, "Udløbet Direkte A")
    b = await _create_movie(client, "Udløbet Direkte B")
    poll = (await _create_poll(client, [a, b])).json()
    await db["polls"].update_one(
        {"_id": ObjectId(poll["id"])},
        {"$set": {"voting_deadline": datetime(2020, 1, 1, tzinfo=timezone.utc)}},
    )

    response = await client.get(f"/api/polls/{poll['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


async def test_expired_poll_computes_a_winner_once_auto_closed(client, db):
    voter1 = await _member(client, "poll_autoclose_v1")
    voter2 = await _member(client, "poll_autoclose_v2")
    a = await _create_movie(client, "Autovinder A")
    b = await _create_movie(client, "Autovinder B")
    poll = (await _create_poll(client, [a, b])).json()
    await voter1.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    await voter2.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    await db["polls"].update_one(
        {"_id": ObjectId(poll["id"])},
        {"$set": {"voting_deadline": datetime(2020, 1, 1, tzinfo=timezone.utc)}},
    )

    response = await client.get(f"/api/polls/{poll['id']}")
    body = response.json()
    assert body["status"] == "closed"
    assert body["winner_indices"] == [0]
    await voter1.aclose()
    await voter2.aclose()


async def test_voting_after_the_deadline_is_rejected_and_closes_the_poll(client, db):
    a = await _create_movie(client, "Sen Stemme A")
    b = await _create_movie(client, "Sen Stemme B")
    poll = (await _create_poll(client, [a, b])).json()
    await db["polls"].update_one(
        {"_id": ObjectId(poll["id"])},
        {"$set": {"voting_deadline": datetime(2020, 1, 1, tzinfo=timezone.utc)}},
    )

    response = await client.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    assert response.status_code == 409

    poll_after = (await client.get(f"/api/polls/{poll['id']}")).json()
    assert poll_after["status"] == "closed"


async def test_auto_closing_notifies_every_voter(client, db, monkeypatch):
    """Samme notifikation som en admins manuelle 'Luk afstemning'
    (test_closing_a_poll_notifies_every_voter ovenfor) — voteren skal ikke
    kunne se forskel på at admin lukkede den og at fristen udløb."""
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    voter = await _member(client, "poll_notify_autoclose")
    a = await _create_movie(client, "Autoluk Besked A")
    b = await _create_movie(client, "Autoluk Besked B")
    poll = (await _create_poll(client, [a, b])).json()
    await voter.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 0})
    await db["polls"].update_one(
        {"_id": ObjectId(poll["id"])},
        {"$set": {"voting_deadline": datetime(2020, 1, 1, tzinfo=timezone.utc)}},
    )

    await client.get(f"/api/polls/{poll['id']}")  # udløser den lazy auto-lukning

    inbox = (await voter.get("/api/messages/inbox")).json()
    assert any(m["subject"] == "Afstemningen er afgjort" for m in inbox)
    assert len(calls) == 1
    await voter.aclose()


async def test_a_closed_poll_cannot_be_auto_closed_again(client, db):
    """En allerede lukket afstemning (manuelt eller ved en tidligere udløbet
    frist) må aldrig sende en ny 'afgjort'-notifikation ved efterfølgende
    opslag — _auto_close_if_expired skal ikke røre en afstemning der ikke
    længere er 'open'."""
    a = await _create_movie(client, "Dobbelt Auto A")
    b = await _create_movie(client, "Dobbelt Auto B")
    poll = (await _create_poll(client, [a, b])).json()
    await db["polls"].update_one(
        {"_id": ObjectId(poll["id"])},
        {"$set": {"voting_deadline": datetime(2020, 1, 1, tzinfo=timezone.utc)}},
    )
    await client.get(f"/api/polls/{poll['id']}")  # første opslag lukker den

    response = await client.get(f"/api/polls/{poll['id']}")
    assert response.json()["status"] == "closed"
    assert response.json()["closed_at"] is not None


# Feature #218 (Jan: "andre guester skal kun indsætte ny film forslag til
# afsteming i en relateret kørende afsteming, en adm skal dog godkende at
# ændring er ok, adm skal selvfølgelig også kunne laver samme tilretning
# som guester men skal dog ikke godkendes af en anden adm").


async def test_nonadmin_suggesting_a_candidate_goes_to_pending_candidates(client):
    guest = await _member(client, "poll_suggest_v1")
    a = await _create_movie(client, "Forslag A")
    b = await _create_movie(client, "Forslag B")
    c = await _create_movie(client, "Forslag C")
    poll = (await _create_poll(client, [a, b])).json()  # admin-oprettet, 'open'

    response = await guest.post(
        f"/api/polls/{poll['id']}/candidates/suggest",
        json={"media_kind": "movie", "movie_id": c},
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["candidates"]) == 2
    assert len(body["pending_candidates"]) == 1
    assert body["pending_candidates"][0]["movie_id"] == c
    assert body["pending_candidates"][0]["suggested_by"] == "poll_suggest_v1"
    assert body["pending_candidates"][0]["title"] == "Forslag C"
    await guest.aclose()


async def test_admin_suggesting_a_candidate_is_added_directly(client):
    a = await _create_movie(client, "Direkte A")
    b = await _create_movie(client, "Direkte B")
    c = await _create_movie(client, "Direkte C")
    poll = (await _create_poll(client, [a, b])).json()

    response = await client.post(
        f"/api/polls/{poll['id']}/candidates/suggest",
        json={"media_kind": "movie", "movie_id": c},
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["candidates"]) == 3
    assert body["pending_candidates"] == []


async def test_the_original_poll_creator_still_needs_approval_for_further_candidates(client):
    """Jan, ved et opklarende spørgsmål: den oprindelige forslagsstiller er
    IKKE undtaget — samme regel som alle andre ikke-admins, selv for deres
    egen (nu godkendte, kørende) afstemning."""
    creator = await _member(client, "poll_own_creator")
    a = await _create_movie(client, "Egen A")
    b = await _create_movie(client, "Egen B")
    c = await _create_movie(client, "Egen C")
    created = (await _create_poll(creator, [a, b])).json()
    assert created["status"] == "pending"
    poll_id = created["id"]
    await client.post(f"/api/polls/{poll_id}/approve")

    response = await creator.post(
        f"/api/polls/{poll_id}/candidates/suggest",
        json={"media_kind": "movie", "movie_id": c},
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["candidates"]) == 2
    assert len(body["pending_candidates"]) == 1
    await creator.aclose()


async def test_suggesting_a_candidate_requires_an_open_poll(client):
    guest = await _member(client, "poll_suggest_notopen")
    a = await _create_movie(client, "Ikke Åben A")
    b = await _create_movie(client, "Ikke Åben B")
    c = await _create_movie(client, "Ikke Åben C")
    poll = (await _create_poll(client, [a, b])).json()
    await client.post(f"/api/polls/{poll['id']}/close")

    response = await guest.post(
        f"/api/polls/{poll['id']}/candidates/suggest",
        json={"media_kind": "movie", "movie_id": c},
    )
    assert response.status_code == 409
    await guest.aclose()


async def test_suggesting_an_already_existing_candidate_is_rejected(client):
    a = await _create_movie(client, "Dubleret A")
    b = await _create_movie(client, "Dubleret B")
    poll = (await _create_poll(client, [a, b])).json()

    response = await client.post(
        f"/api/polls/{poll['id']}/candidates/suggest",
        json={"media_kind": "movie", "movie_id": a},
    )
    assert response.status_code == 409


async def test_suggesting_an_already_pending_candidate_is_rejected(client):
    guest1 = await _member(client, "poll_suggest_dup1")
    guest2 = await _member(client, "poll_suggest_dup2")
    a = await _create_movie(client, "Dobbeltforslag A")
    b = await _create_movie(client, "Dobbeltforslag B")
    c = await _create_movie(client, "Dobbeltforslag C")
    poll = (await _create_poll(client, [a, b])).json()
    await guest1.post(
        f"/api/polls/{poll['id']}/candidates/suggest", json={"media_kind": "movie", "movie_id": c}
    )

    response = await guest2.post(
        f"/api/polls/{poll['id']}/candidates/suggest", json={"media_kind": "movie", "movie_id": c}
    )
    assert response.status_code == 409
    await guest1.aclose()
    await guest2.aclose()


async def test_admin_can_approve_a_candidate_suggestion(client):
    guest = await _member(client, "poll_approve_suggest")
    a = await _create_movie(client, "Godkend A")
    b = await _create_movie(client, "Godkend B")
    c = await _create_movie(client, "Godkend C")
    poll = (await _create_poll(client, [a, b])).json()
    suggested = (
        await guest.post(
            f"/api/polls/{poll['id']}/candidates/suggest", json={"media_kind": "movie", "movie_id": c}
        )
    ).json()
    suggestion_id = suggested["pending_candidates"][0]["suggestion_id"]

    response = await client.post(f"/api/polls/{poll['id']}/pending-candidates/{suggestion_id}/approve")
    assert response.status_code == 200
    body = response.json()
    assert len(body["candidates"]) == 3
    assert body["pending_candidates"] == []
    await guest.aclose()


async def test_admin_can_reject_a_candidate_suggestion(client):
    guest = await _member(client, "poll_reject_suggest")
    a = await _create_movie(client, "Afvis A")
    b = await _create_movie(client, "Afvis B")
    c = await _create_movie(client, "Afvis C")
    poll = (await _create_poll(client, [a, b])).json()
    suggested = (
        await guest.post(
            f"/api/polls/{poll['id']}/candidates/suggest", json={"media_kind": "movie", "movie_id": c}
        )
    ).json()
    suggestion_id = suggested["pending_candidates"][0]["suggestion_id"]

    response = await client.delete(f"/api/polls/{poll['id']}/pending-candidates/{suggestion_id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["candidates"]) == 2
    assert body["pending_candidates"] == []
    await guest.aclose()


async def test_nonadmin_cannot_approve_or_reject_a_suggestion(client):
    guest = await _member(client, "poll_no_approve")
    a = await _create_movie(client, "Ej Godkend A")
    b = await _create_movie(client, "Ej Godkend B")
    c = await _create_movie(client, "Ej Godkend C")
    poll = (await _create_poll(client, [a, b])).json()
    suggested = (
        await guest.post(
            f"/api/polls/{poll['id']}/candidates/suggest", json={"media_kind": "movie", "movie_id": c}
        )
    ).json()
    suggestion_id = suggested["pending_candidates"][0]["suggestion_id"]

    approve_response = await guest.post(
        f"/api/polls/{poll['id']}/pending-candidates/{suggestion_id}/approve"
    )
    assert approve_response.status_code == 403
    reject_response = await guest.delete(f"/api/polls/{poll['id']}/pending-candidates/{suggestion_id}")
    assert reject_response.status_code == 403
    await guest.aclose()


async def test_approving_an_unknown_suggestion_id_404s(client):
    a = await _create_movie(client, "Ukendt A")
    b = await _create_movie(client, "Ukendt B")
    poll = (await _create_poll(client, [a, b])).json()

    response = await client.post(f"/api/polls/{poll['id']}/pending-candidates/{ObjectId()}/approve")
    assert response.status_code == 404


async def test_a_newly_approved_candidate_can_immediately_be_voted_on(client):
    guest = await _member(client, "poll_vote_new_candidate")
    a = await _create_movie(client, "Ny Stem A")
    b = await _create_movie(client, "Ny Stem B")
    c = await _create_movie(client, "Ny Stem C")
    poll = (await _create_poll(client, [a, b])).json()
    suggested = (
        await guest.post(
            f"/api/polls/{poll['id']}/candidates/suggest", json={"media_kind": "movie", "movie_id": c}
        )
    ).json()
    suggestion_id = suggested["pending_candidates"][0]["suggestion_id"]
    await client.post(f"/api/polls/{poll['id']}/pending-candidates/{suggestion_id}/approve")

    response = await guest.post(f"/api/polls/{poll['id']}/vote", json={"candidate_index": 2})
    assert response.status_code == 200
    assert response.json()["candidates"][2]["vote_count"] == 1
    await guest.aclose()


async def test_admin_is_notified_of_a_new_candidate_suggestion(client):
    """Samme in-app-only afprøvning som de øvrige notify_admins_new_*-tests
    — admin-fixturen har ingen e-mail sat."""
    guest = await _member(client, "poll_notify_suggest_admin")
    a = await _create_movie(client, "Meld Kandidat A")
    b = await _create_movie(client, "Meld Kandidat B")
    c = await _create_movie(client, "Meld Kandidat C")
    poll = (await _create_poll(client, [a, b])).json()

    await guest.post(
        f"/api/polls/{poll['id']}/candidates/suggest", json={"media_kind": "movie", "movie_id": c}
    )

    admin_inbox = (await client.get("/api/messages/inbox")).json()
    assert any(m["subject"] == "Nyt kandidat-forslag afventer godkendelse" for m in admin_inbox)
    await guest.aclose()


async def test_suggester_is_notified_when_their_candidate_is_approved(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    guest = await _member(client, "poll_notify_approved_suggest")
    a = await _create_movie(client, "Godkend Besked A")
    b = await _create_movie(client, "Godkend Besked B")
    c = await _create_movie(client, "Godkend Besked C")
    poll = (await _create_poll(client, [a, b])).json()
    suggested = (
        await guest.post(
            f"/api/polls/{poll['id']}/candidates/suggest", json={"media_kind": "movie", "movie_id": c}
        )
    ).json()
    suggestion_id = suggested["pending_candidates"][0]["suggestion_id"]

    await client.post(f"/api/polls/{poll['id']}/pending-candidates/{suggestion_id}/approve")

    inbox = (await guest.get("/api/messages/inbox")).json()
    assert any(m["subject"] == "Dit kandidat-forslag er godkendt" for m in inbox)
    assert len(calls) == 1
    await guest.aclose()


async def test_suggester_is_notified_when_their_candidate_is_rejected(client, monkeypatch):
    _configure_resend(monkeypatch)
    calls = _capture_email(monkeypatch)
    guest = await _member(client, "poll_notify_rejected_suggest")
    a = await _create_movie(client, "Afvis Besked A")
    b = await _create_movie(client, "Afvis Besked B")
    c = await _create_movie(client, "Afvis Besked C")
    poll = (await _create_poll(client, [a, b])).json()
    suggested = (
        await guest.post(
            f"/api/polls/{poll['id']}/candidates/suggest", json={"media_kind": "movie", "movie_id": c}
        )
    ).json()
    suggestion_id = suggested["pending_candidates"][0]["suggestion_id"]

    await client.delete(f"/api/polls/{poll['id']}/pending-candidates/{suggestion_id}")

    inbox = (await guest.get("/api/messages/inbox")).json()
    assert any(m["subject"] == "Om dit kandidat-forslag" for m in inbox)
    assert len(calls) == 1
    await guest.aclose()
