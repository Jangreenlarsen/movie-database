from httpx import ASGITransport, AsyncClient

from app.main import app


async def _create_movie(client, title="Reservation Movie"):
    created = await client.post(
        "/api/movies", json={"title": title, "media_type": "Fysisk", "format": "F-DVD"}
    )
    return created.json()["id"]


async def _create_screening(client, movie_id, when="2099-09-01T20:00:00"):
    created = await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": when},
    )
    return created.json()["id"]


async def _member_client(admin_client, username, role=None):
    """Registers a fresh user, approves them (feature #66) and optionally
    promotes them to a role (e.g. guest). Returns a logged-in AsyncClient."""
    transport = ASGITransport(app=app)
    member = AsyncClient(transport=transport, base_url="http://test")
    register = await member.post(
        "/api/auth/register", json={"username": username, "password": "testpassword123"}
    )
    user_id = register.json()["id"]
    await admin_client.patch(f"/api/users/{user_id}/status", json={"status": "active"})
    if role:
        await admin_client.patch(f"/api/users/{user_id}/role", json={"role": role})
    return member


def _status_of(seat_map, seat_id):
    return next(s["status"] for s in seat_map["seats"] if s["seat_id"] == seat_id)


async def test_seat_map_lists_all_14_seats_free(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)

    response = await client.get(f"/api/screenings/{screening_id}/seats")
    assert response.status_code == 200
    seats = response.json()["seats"]
    assert len(seats) == 14
    assert [s["number"] for s in seats] == list(range(1, 15))
    assert all(s["status"] == "free" for s in seats)


async def test_seat_map_requires_login(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    # A fresh client with no cookie (the shared `client`/`raw_client` fixture
    # object is already logged in once `client` has registered on it).
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as anon:
        response = await anon.get(f"/api/screenings/{screening_id}/seats")
        assert response.status_code == 401


async def test_seat_map_for_unknown_screening_404(client):
    response = await client.get("/api/screenings/000000000000000000000000/seats")
    assert response.status_code == 404


async def test_guest_can_reserve_and_sees_it_as_mine(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "guest_res", role="guest")

    response = await guest.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1", "N2-1"]}
    )
    assert response.status_code == 201
    created = response.json()
    assert {r["seat_id"] for r in created} == {"N1-1", "N2-1"}
    assert all(r["status"] == "pending" for r in created)
    assert all(r["reserved_by"] == "guest_res" for r in created)

    seat_map = (await guest.get(f"/api/screenings/{screening_id}/seats")).json()
    entry = next(s for s in seat_map["seats"] if s["seat_id"] == "N1-1")
    assert entry["status"] == "mine"
    assert entry["approved"] is False
    assert entry["reservation_id"]
    await guest.aclose()


async def test_reserved_seat_shows_pending_then_taken_to_others(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "guest_a", role="guest")
    other = await _member_client(client, "member_b")

    reservation = (
        await guest.post(
            f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N3-3"]}
        )
    ).json()[0]

    # Another user sees it as an unavailable pending seat, not "mine".
    other_map = (await other.get(f"/api/screenings/{screening_id}/seats")).json()
    assert _status_of(other_map, "N3-3") == "pending"

    await client.post(f"/api/reservations/{reservation['id']}/approve")

    other_map = (await other.get(f"/api/screenings/{screening_id}/seats")).json()
    assert _status_of(other_map, "N3-3") == "taken"
    await guest.aclose()
    await other.aclose()


async def test_cannot_double_book_a_seat_and_no_partial_reservation(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    first = await _member_client(client, "first", role="guest")
    second = await _member_client(client, "second", role="guest")

    await first.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-2"]}
    )

    # Second user asks for a free seat AND the taken one — the whole request
    # must fail (409) without reserving the free seat either.
    response = await second.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-3", "N1-2"]}
    )
    assert response.status_code == 409

    seat_map = (await second.get(f"/api/screenings/{screening_id}/seats")).json()
    assert _status_of(seat_map, "N1-3") == "free"
    await first.aclose()
    await second.aclose()


async def test_reserving_same_seat_twice_is_idempotent(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "repeat_guest", role="guest")

    await guest.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N2-4"]}
    )
    again = await guest.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N2-4"]}
    )
    assert again.status_code == 201

    mine = (await guest.get("/api/reservations/mine")).json()
    assert len([r for r in mine if r["seat_id"] == "N2-4"]) == 1
    await guest.aclose()


async def test_invalid_seat_id_is_rejected(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    response = await client.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["Z9-9"]}
    )
    assert response.status_code == 400


async def test_reserve_for_unknown_screening_404(client):
    response = await client.post(
        "/api/screenings/000000000000000000000000/reservations",
        json={"seat_ids": ["N1-1"]},
    )
    assert response.status_code == 404


async def test_approve_requires_admin(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_approve", role="guest")
    reservation = (
        await guest.post(
            f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]}
        )
    ).json()[0]

    member = await _member_client(client, "m_approve")
    response = await member.post(f"/api/reservations/{reservation['id']}/approve")
    assert response.status_code == 403
    await guest.aclose()
    await member.aclose()


async def test_admin_lists_pending_and_approves(client):
    movie_id = await _create_movie(client, "Konduktør Film")
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_queue", role="guest")
    await guest.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N2-2"]}
    )

    pending = await client.get("/api/reservations", params={"status": "pending"})
    assert pending.status_code == 200
    rows = pending.json()
    assert len(rows) == 1
    assert rows[0]["seat_number"] == 6
    assert rows[0]["screening_title"] == "Konduktør Film"

    approved = await client.post(f"/api/reservations/{rows[0]['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == "testuser"
    await guest.aclose()


async def test_list_reservations_requires_admin(client):
    member = await _member_client(client, "m_list")
    response = await member.get("/api/reservations")
    assert response.status_code == 403
    await member.aclose()


async def test_owner_can_cancel_but_stranger_cannot(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    owner = await _member_client(client, "owner", role="guest")
    stranger = await _member_client(client, "stranger", role="guest")

    reservation = (
        await owner.post(
            f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-4"]}
        )
    ).json()[0]

    # A stranger cannot delete someone else's reservation.
    assert (await stranger.delete(f"/api/reservations/{reservation['id']}")).status_code == 403

    # The owner can, and the seat frees up again.
    assert (await owner.delete(f"/api/reservations/{reservation['id']}")).status_code == 204
    seat_map = (await owner.get(f"/api/screenings/{screening_id}/seats")).json()
    assert _status_of(seat_map, "N1-4") == "free"
    await owner.aclose()
    await stranger.aclose()


async def test_admin_can_cancel_any_reservation(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_admincancel", role="guest")
    reservation = (
        await guest.post(
            f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N3-1"]}
        )
    ).json()[0]

    assert (await client.delete(f"/api/reservations/{reservation['id']}")).status_code == 204
    await guest.aclose()


async def test_global_hold_blocks_seat_on_every_screening(client):
    movie_id = await _create_movie(client)
    screening_a = await _create_screening(client, movie_id, "2099-09-01T20:00:00")
    screening_b = await _create_screening(client, movie_id, "2099-09-08T20:00:00")

    hold = await client.post("/api/reservations/hold", json={"seat_id": "N1-1", "scope": "global"})
    assert hold.status_code == 201
    assert hold.json()["is_hold"] is True

    for screening_id in (screening_a, screening_b):
        seat_map = (await client.get(f"/api/screenings/{screening_id}/seats")).json()
        assert _status_of(seat_map, "N1-1") == "taken"

    guest = await _member_client(client, "g_hold", role="guest")
    blocked = await guest.post(
        f"/api/screenings/{screening_a}/reservations", json={"seat_ids": ["N1-1"]}
    )
    assert blocked.status_code == 409
    await guest.aclose()


async def test_screening_specific_hold_only_blocks_that_screening(client):
    movie_id = await _create_movie(client)
    screening_a = await _create_screening(client, movie_id, "2099-09-01T20:00:00")
    screening_b = await _create_screening(client, movie_id, "2099-09-08T20:00:00")

    hold = await client.post(
        "/api/reservations/hold",
        json={"seat_id": "N2-3", "scope": "screening", "screening_id": screening_a},
    )
    assert hold.status_code == 201

    map_a = (await client.get(f"/api/screenings/{screening_a}/seats")).json()
    map_b = (await client.get(f"/api/screenings/{screening_b}/seats")).json()
    assert _status_of(map_a, "N2-3") == "taken"
    assert _status_of(map_b, "N2-3") == "free"


async def test_hold_requires_admin(client):
    member = await _member_client(client, "m_hold")
    response = await member.post("/api/reservations/hold", json={"seat_id": "N1-1", "scope": "global"})
    assert response.status_code == 403
    await member.aclose()


async def test_screening_hold_without_screening_id_is_rejected(client):
    response = await client.post(
        "/api/reservations/hold", json={"seat_id": "N1-1", "scope": "screening"}
    )
    assert response.status_code == 422


async def test_deleting_screening_removes_its_reservations(client):
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_del", role="guest")
    await guest.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1", "N2-1"]}
    )

    assert len((await client.get("/api/reservations")).json()) == 2

    await client.delete(f"/api/screenings/{screening_id}")
    assert (await client.get("/api/reservations")).json() == []
    await guest.aclose()


async def test_approving_notifies_the_owner(client):
    """Feature #134 — når konduktøren godkender, får ejeren en besked i
    indbakken (genbruger feature #100's besked-system)."""
    movie_id = await _create_movie(client, "Notifikations Film")
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_notify", role="guest")
    reservation = (
        await guest.post(
            f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N2-3"]}
        )
    ).json()[0]

    # Ingen besked før godkendelsen.
    assert (await guest.get("/api/messages/inbox")).json() == []

    await client.post(f"/api/reservations/{reservation['id']}/approve")

    inbox = (await guest.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    assert inbox[0]["subject"] == "Din pladsreservation er godkendt"
    assert "sæde 7" in inbox[0]["body"].lower()  # N2-3 = sæde 7
    assert "Notifikations Film" in inbox[0]["body"]
    await guest.aclose()


async def test_past_screening_reservations_are_cleaned_up_on_list(client):
    """Feature #167 — Jan: "de film [der] har kørt skal også have slettet
    deres sæde reservation når en film er vist". Ingen tidsstyret job findes
    i appen, så oprydningen sker ved næste læsning af reservations-listen."""
    movie_id = await _create_movie(client, "Afholdt Film")
    screening_id = await _create_screening(client, movie_id, "2020-01-01T20:00:00")
    guest = await _member_client(client, "g_past", role="guest")
    created = await guest.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]}
    )
    # Forudsætning: reservationen blev faktisk oprettet. (Tjekket her via
    # svaret, ikke /mine — siden feature #227 rydder /mine selv op.)
    assert created.status_code == 201

    assert (await client.get("/api/reservations")).json() == []
    await guest.aclose()


async def test_upcoming_screening_reservations_survive_the_cleanup(client):
    movie_id = await _create_movie(client, "Kommende Film")
    screening_id = await _create_screening(client, movie_id)  # default: far i fremtiden
    guest = await _member_client(client, "g_upcoming", role="guest")
    await guest.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]}
    )

    reservations = (await client.get("/api/reservations")).json()
    assert len(reservations) == 1
    await guest.aclose()


async def test_global_holds_survive_past_screening_cleanup(client):
    """Et globalt hold (screening_id: None) hører ikke til nogen bestemt
    fremvisning og må derfor aldrig rammes af oprydningen, uanset hvor mange
    afholdte fremvisninger der findes."""
    movie_id = await _create_movie(client, "Afholdt Film 2")
    screening_id = await _create_screening(client, movie_id, "2020-01-01T20:00:00")
    guest = await _member_client(client, "g_past2", role="guest")
    await guest.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]}
    )
    await client.post("/api/reservations/hold", json={"seat_id": "N2-2", "scope": "global"})

    reservations = (await client.get("/api/reservations")).json()
    assert len(reservations) == 1
    assert reservations[0]["scope"] == "global"
    await guest.aclose()


async def test_list_approved_includes_holds_and_guest_reservations(client):
    """Feature #137 — konduktørens 'godkendte / for-reserverede'-liste henter
    ?status=approved; både en godkendt gæste-reservation og et admin-hold har
    status 'approved', så begge skal med (så de kan tilbagetrækkes)."""
    movie_id = await _create_movie(client)
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_appr_list", role="guest")
    reservation = (
        await guest.post(
            f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]}
        )
    ).json()[0]
    await client.post(f"/api/reservations/{reservation['id']}/approve")
    await client.post("/api/reservations/hold", json={"seat_id": "N2-2", "scope": "global"})

    approved = (
        await client.get("/api/reservations", params={"status": "approved"})
    ).json()
    assert sorted(r["seat_number"] for r in approved) == [1, 6]  # sæde 1 + sæde 6 (hold)
    holds = [r for r in approved if r["is_hold"]]
    assert len(holds) == 1 and holds[0]["scope"] == "global"

    # Tilbagetræk hold'et → sædet er frit igen.
    await client.delete(f"/api/reservations/{holds[0]['id']}")
    still_approved = (
        await client.get("/api/reservations", params={"status": "approved"})
    ).json()
    assert [r["seat_number"] for r in still_approved] == [1]
    await guest.aclose()


# Feature #170 — private arrangementer: gæst-rollen kan ikke booke sæder på
# en visning admin har markeret som privat.


async def test_admin_can_create_private_screening(client):
    movie_id = await _create_movie(client, "Privat Film")
    created = await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2099-09-01T20:00:00", "is_private": True},
    )
    assert created.status_code == 201
    assert created.json()["is_private"] is True


async def test_screening_defaults_to_not_private(client):
    movie_id = await _create_movie(client, "Almindelig Film")
    screening_id = await _create_screening(client, movie_id)
    resp = await client.get("/api/screenings")
    screening = next(s for s in resp.json() if s["id"] == screening_id)
    assert screening["is_private"] is False


async def test_admin_can_toggle_private_via_update(client):
    movie_id = await _create_movie(client, "Skift Privat Film")
    screening_id = await _create_screening(client, movie_id)
    updated = await client.patch(f"/api/screenings/{screening_id}", json={"is_private": True})
    assert updated.json()["is_private"] is True
    reverted = await client.patch(f"/api/screenings/{screening_id}", json={"is_private": False})
    assert reverted.json()["is_private"] is False


async def test_guest_cannot_reserve_seat_on_private_screening(client):
    movie_id = await _create_movie(client, "Privat Reservation Film")
    created = await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2099-09-01T20:00:00", "is_private": True},
    )
    screening_id = created.json()["id"]
    guest = await _member_client(client, "g_private_blocked", role="guest")

    resp = await guest.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]}
    )
    assert resp.status_code == 403
    # Ingen delvis reservation blev alligevel oprettet.
    assert (await client.get("/api/reservations")).json() == []
    await guest.aclose()


async def test_standard_user_can_still_reserve_on_private_screening(client):
    """Kun gæst-rollen er blokeret — et almindeligt medlem af husstanden
    (rollen 'standard') skal stadig kunne booke et privat arrangement."""
    movie_id = await _create_movie(client, "Privat Standard Film")
    created = await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2099-09-01T20:00:00", "is_private": True},
    )
    screening_id = created.json()["id"]
    # Feature #175 — registration now defaults to guest, so "standard" must
    # be requested explicitly; the old "ingen rolle = standard" shortcut no
    # longer holds.
    member = await _member_client(client, "std_private_ok", role="standard")

    resp = await member.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]}
    )
    assert resp.status_code == 201
    await member.aclose()


async def test_guest_can_still_reserve_on_a_non_private_screening(client):
    """Regression: den almindelige (ikke-private) sti er uændret."""
    movie_id = await _create_movie(client, "Stadig Offentlig Film")
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_still_open", role="guest")

    resp = await guest.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]}
    )
    assert resp.status_code == 201
    await guest.aclose()


# --- Feature #227: "Mine pladser" + admin-tilmeldte pr. visning -------------


async def test_my_reservations_includes_own_holds(client):
    """BUGS.md #100 — admins egne for-reserveringer står i "Mine pladser",
    både det globale hold (øverst) og hold på en enkelt visning."""
    movie_id = await _create_movie(client, "Hold Er Mine")
    screening_id = await _create_screening(client, movie_id)
    await client.post(
        f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]}
    )
    await client.post("/api/reservations/hold", json={"seat_id": "N3-5", "scope": "global"})
    await client.post(
        "/api/reservations/hold",
        json={"seat_id": "N2-1", "scope": "screening", "screening_id": screening_id},
    )

    mine = (await client.get("/api/reservations/mine")).json()
    assert mine[0]["seat_id"] == "N3-5"
    assert mine[0]["is_hold"] is True and mine[0]["screening_id"] is None
    assert sorted(r["seat_id"] for r in mine[1:]) == ["N1-1", "N2-1"]
    assert all(r["screening_id"] == screening_id for r in mine[1:])


async def test_admin_holds_not_shown_to_other_users(client):
    movie_id = await _create_movie(client, "Hold Andres")
    await _create_screening(client, movie_id)
    await client.post("/api/reservations/hold", json={"seat_id": "N3-5", "scope": "global"})
    guest = await _member_client(client, "g_no_holds", role="guest")
    assert (await guest.get("/api/reservations/mine")).json() == []
    await guest.aclose()


async def test_admin_can_release_own_hold_without_notifying(client):
    """At frigive sit eget hold fra "Mine pladser" er en admin-handling —
    konduktøren (admin selv) skal ikke have en fraværs-besked."""
    held = (
        await client.post("/api/reservations/hold", json={"seat_id": "N3-5", "scope": "global"})
    ).json()
    response = await client.delete(f"/api/reservations/{held['id']}")
    assert response.status_code == 204
    assert (await client.get("/api/reservations/mine")).json() == []


async def test_my_reservations_cleans_up_past_screenings(client):
    movie_id = await _create_movie(client, "Mine Afholdt")
    past_id = await _create_screening(client, movie_id, "2020-01-01T20:00:00")
    guest = await _member_client(client, "g_mine_past", role="guest")
    await guest.post(f"/api/screenings/{past_id}/reservations", json={"seat_ids": ["N1-1"]})

    assert (await guest.get("/api/reservations/mine")).json() == []
    # Og den er faktisk slettet, ikke bare skjult.
    assert (await client.get("/api/reservations")).json() == []
    await guest.aclose()


async def test_my_reservations_sorted_by_screening_time(client):
    movie_id = await _create_movie(client, "Sortering")
    later = await _create_screening(client, movie_id, "2099-12-01T20:00:00")
    sooner = await _create_screening(client, movie_id, "2099-10-01T20:00:00")
    guest = await _member_client(client, "g_sorted", role="guest")
    await guest.post(f"/api/screenings/{later}/reservations", json={"seat_ids": ["N1-1"]})
    await guest.post(f"/api/screenings/{sooner}/reservations", json={"seat_ids": ["N2-2", "N2-1"]})

    mine = (await guest.get("/api/reservations/mine")).json()
    assert [(r["screening_id"], r["seat_number"]) for r in mine] == [
        (sooner, 5),
        (sooner, 6),
        (later, 1),
    ]
    await guest.aclose()


async def test_owner_can_cancel_an_approved_reservation(client):
    """At melde fra gælder også en godkendt plads — det er hele pointen."""
    movie_id = await _create_movie(client, "Meld Fra Godkendt")
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_cancel_ok", role="guest")
    created = (
        await guest.post(f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-2"]})
    ).json()
    await client.post(f"/api/reservations/{created[0]['id']}/approve")

    response = await guest.delete(f"/api/reservations/{created[0]['id']}")
    assert response.status_code == 204
    assert (await guest.get("/api/reservations/mine")).json() == []
    await guest.aclose()


async def test_cancelling_an_approved_seat_notifies_admins(client):
    movie_id = await _create_movie(client, "Besked Til Konduktør")
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_notify_admin", role="guest")
    created = (
        await guest.post(f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N2-3"]})
    ).json()
    await client.post(f"/api/reservations/{created[0]['id']}/approve")

    await guest.delete(f"/api/reservations/{created[0]['id']}")

    inbox = (await client.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    assert inbox[0]["subject"] == "Plads frigivet i Voldby BIO"
    assert "g_notify_admin" in inbox[0]["body"]
    assert "sæde 7" in inbox[0]["body"]
    assert "Besked Til Konduktør" in inbox[0]["body"]
    await guest.aclose()


async def test_cancelling_a_pending_seat_does_not_notify_admins(client):
    """En afventende plads var aldrig lovet væk — ingen støj til admin."""
    movie_id = await _create_movie(client, "Ingen Støj")
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_pending_quiet", role="guest")
    created = (
        await guest.post(f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N2-4"]})
    ).json()

    await guest.delete(f"/api/reservations/{created[0]['id']}")

    assert (await client.get("/api/messages/inbox")).json() == []
    await guest.aclose()


async def test_admin_can_reserve_on_behalf_of_a_user(client):
    movie_id = await _create_movie(client, "På Vegne Af")
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_behalf", role="guest")

    response = await client.post(
        f"/api/screenings/{screening_id}/reservations",
        json={"seat_ids": ["N1-3"], "reserved_for": "G_Behalf"},
    )
    assert response.status_code == 201
    created = response.json()
    assert created[0]["reserved_by"] == "g_behalf"
    assert created[0]["status"] == "approved"
    assert created[0]["approved_by"] == "testuser"
    assert created[0]["is_hold"] is False

    mine = (await guest.get("/api/reservations/mine")).json()
    assert [r["seat_id"] for r in mine] == ["N1-3"]

    inbox = (await guest.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    assert inbox[0]["subject"] == "Du har fået en plads i Voldby BIO"
    assert "sæde 3" in inbox[0]["body"]
    await guest.aclose()


async def test_non_admin_cannot_reserve_on_behalf_of_others(client):
    """Håndhævet i backend, ikke kun ved at skjule formularen (regel 16)."""
    movie_id = await _create_movie(client, "Ikke For Andre")
    screening_id = await _create_screening(client, movie_id)
    member = await _member_client(client, "std_behalf", role="standard")
    victim = await _member_client(client, "victim_behalf", role="guest")

    response = await member.post(
        f"/api/screenings/{screening_id}/reservations",
        json={"seat_ids": ["N1-1"], "reserved_for": "victim_behalf"},
    )
    assert response.status_code == 403
    assert (await client.get("/api/reservations")).json() == []
    await member.aclose()
    await victim.aclose()


async def test_reserving_for_an_unknown_user_is_a_clear_400(client):
    movie_id = await _create_movie(client, "Ukendt Bruger")
    screening_id = await _create_screening(client, movie_id)

    response = await client.post(
        f"/api/screenings/{screening_id}/reservations",
        json={"seat_ids": ["N1-1"], "reserved_for": "findes_ikke"},
    )
    assert response.status_code == 400
    assert "findes ikke" in response.json()["detail"]
    assert (await client.get("/api/reservations")).json() == []


async def test_reserving_for_an_inactive_user_is_rejected(client):
    movie_id = await _create_movie(client, "Spærret Bruger")
    screening_id = await _create_screening(client, movie_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as pending:
        # Registreret men aldrig godkendt: status "pending".
        await pending.post(
            "/api/auth/register", json={"username": "still_pending", "password": "testpassword123"}
        )

    response = await client.post(
        f"/api/screenings/{screening_id}/reservations",
        json={"seat_ids": ["N1-1"], "reserved_for": "still_pending"},
    )
    assert response.status_code == 400
    assert "ikke aktiv" in response.json()["detail"]


async def test_blank_reserved_for_means_a_normal_own_reservation(client):
    """Tom streng/whitespace er "ikke sat" — ikke et opslag på brugeren ''."""
    movie_id = await _create_movie(client, "Blank Felt")
    screening_id = await _create_screening(client, movie_id)

    response = await client.post(
        f"/api/screenings/{screening_id}/reservations",
        json={"seat_ids": ["N1-1"], "reserved_for": "   "},
    )
    assert response.status_code == 201
    assert response.json()[0]["reserved_by"] == "testuser"
    assert response.json()[0]["status"] == "pending"


async def test_admin_adding_a_user_on_a_taken_seat_is_409(client):
    movie_id = await _create_movie(client, "Optaget Sæde")
    screening_id = await _create_screening(client, movie_id)
    first = await _member_client(client, "g_first_seat", role="guest")
    second = await _member_client(client, "g_second_seat", role="guest")
    await first.post(f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]})

    response = await client.post(
        f"/api/screenings/{screening_id}/reservations",
        json={"seat_ids": ["N1-1"], "reserved_for": "g_second_seat"},
    )
    assert response.status_code == 409
    await first.aclose()
    await second.aclose()


async def test_admin_adding_a_user_approves_their_own_pending_seat(client):
    """Har brugeren selv en afventende plads på sædet, godkendes den i stedet
    for at give en 409 på brugerens egen reservation."""
    movie_id = await _create_movie(client, "Egen Afventende")
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_own_pending", role="guest")
    await guest.post(f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N2-5"]})

    response = await client.post(
        f"/api/screenings/{screening_id}/reservations",
        json={"seat_ids": ["N2-5"], "reserved_for": "g_own_pending"},
    )
    assert response.status_code == 201
    assert response.json()[0]["status"] == "approved"
    assert len((await client.get("/api/reservations")).json()) == 1
    await guest.aclose()


async def test_admin_can_clear_all_reservations_on_one_screening(client):
    movie_id = await _create_movie(client, "Ryd Alle")
    target = await _create_screening(client, movie_id, "2099-10-01T20:00:00")
    other = await _create_screening(client, movie_id, "2099-11-01T20:00:00")
    guest = await _member_client(client, "g_clear", role="guest")
    await guest.post(f"/api/screenings/{target}/reservations", json={"seat_ids": ["N1-1", "N1-2"]})
    await guest.post(f"/api/screenings/{other}/reservations", json={"seat_ids": ["N1-1"]})
    await client.post(
        "/api/reservations/hold",
        json={"seat_id": "N3-1", "scope": "screening", "screening_id": target},
    )
    await client.post("/api/reservations/hold", json={"seat_id": "N3-5", "scope": "global"})

    response = await client.delete(f"/api/screenings/{target}/reservations")
    assert response.status_code == 200
    assert response.json() == {"screening_id": target, "removed": 3}

    remaining = (await client.get("/api/reservations")).json()
    # Den anden visnings plads + det globale hold står tilbage.
    assert sorted((r["screening_id"] or "", r["seat_id"]) for r in remaining) == sorted(
        [(other, "N1-1"), ("", "N3-5")]
    )
    await guest.aclose()


async def test_only_admin_can_clear_a_screening(client):
    movie_id = await _create_movie(client, "Ryd Kræver Admin")
    screening_id = await _create_screening(client, movie_id)
    member = await _member_client(client, "std_clear", role="standard")
    await member.post(f"/api/screenings/{screening_id}/reservations", json={"seat_ids": ["N1-1"]})

    response = await member.delete(f"/api/screenings/{screening_id}/reservations")
    assert response.status_code == 403
    assert len((await client.get("/api/reservations")).json()) == 1
    await member.aclose()


async def test_clearing_an_unknown_screening_is_404(client):
    response = await client.delete("/api/screenings/000000000000000000000000/reservations")
    assert response.status_code == 404


async def test_system_backup_keeps_admin_added_reservations(client):
    """Regel 20 — en plads admin har tilføjet (reserved_by = en anden bruger,
    approved_by = admin) skal overleve en system-backup rundtur uændret."""
    movie_id = await _create_movie(client, "Backup Plads")
    screening_id = await _create_screening(client, movie_id)
    guest = await _member_client(client, "g_backup_seat", role="guest")
    await client.post(
        f"/api/screenings/{screening_id}/reservations",
        json={"seat_ids": ["N1-4"], "reserved_for": "g_backup_seat"},
    )

    backup = (await client.get("/api/system/backup")).json()
    saved = [r for r in backup["seat_reservations"] if r["seat_id"] == "N1-4"]
    assert len(saved) == 1
    assert saved[0]["reserved_by"] == "g_backup_seat"
    assert saved[0]["approved_by"] == "testuser"
    assert saved[0]["status"] == "approved"
    await guest.aclose()
