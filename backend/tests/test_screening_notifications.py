"""Feature #202 (Jan: "besked system skal kunne sende hvis user opretter
ønsker til forvisning og ønskeliste og svar skal sendes return hvis adm
lave forandring for de ønsker/forvisninger") — notifikationer for
forvisnings-ønsker: admin får besked når et nyt ønske oprettes (eller en ny
bruger slutter sig til et eksisterende), og den/de der ønskede en titel får
et svar når admin afviser eller planlægger den.
"""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _second_user(client, username="requester"):
    """En ekstra, aktiv, ikke-admin bruger med sin egen session. `client`
    er admin (feature #66's bootstrap)."""
    transport = ASGITransport(app=app)
    other = AsyncClient(transport=transport, base_url="http://test")
    register = await other.post(
        "/api/auth/register", json={"username": username, "password": "testpassword123"}
    )
    await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})
    return other


async def _create_movie(client, title):
    created = await client.post(
        "/api/movies", json={"title": title, "media_type": "Fysisk", "format": "F-DVD"}
    )
    return created.json()["id"]


async def test_admin_is_notified_when_a_user_creates_a_new_screening_request(client):
    movie_id = await _create_movie(client, "Ny Anmodning")
    requester = await _second_user(client, "requester1")

    response = await requester.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )
    assert response.status_code == 201

    inbox = (await client.get("/api/messages/inbox")).json()
    assert any("Ny Anmodning" in m["body"] for m in inbox)
    assert any(m["subject"] == "Nyt ønske om visning i Voldby BIO" for m in inbox)


async def test_admin_is_notified_when_a_different_user_joins_an_existing_request(client):
    movie_id = await _create_movie(client, "Delt Anmodning")
    first = await _second_user(client, "firstjoiner")
    second = await _second_user(client, "secondjoiner")

    await first.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )
    await second.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-02T20:00:00"},
    )

    inbox = (await client.get("/api/messages/inbox")).json()
    new_request_messages = [m for m in inbox if m["subject"] == "Nyt ønske om visning i Voldby BIO"]
    assert len(new_request_messages) == 2


async def test_admin_is_not_notified_again_for_a_repeated_request_from_the_same_user(client):
    movie_id = await _create_movie(client, "Gentaget Anmodning")
    requester = await _second_user(client, "repeatrequester")

    await requester.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )
    # Samme bruger, samme titel igen — add_requester's egen $ne-dedup gør
    # det til et no-op (se screening_service.request_screening's docstring).
    await requester.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )

    inbox = (await client.get("/api/messages/inbox")).json()
    new_request_messages = [m for m in inbox if m["subject"] == "Nyt ønske om visning i Voldby BIO"]
    assert len(new_request_messages) == 1


async def test_requester_is_notified_when_admin_declines_their_request(client):
    movie_id = await _create_movie(client, "Afvist Titel")
    requester = await _second_user(client, "declinedrequester")

    created = await requester.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )
    request_id = created.json()["id"]

    decline = await client.patch(f"/api/screening-requests/{request_id}", json={"status": "declined"})
    assert decline.status_code == 200

    inbox = (await requester.get("/api/messages/inbox")).json()
    assert any("Afvist Titel" in m["body"] for m in inbox)
    assert any("afvist" in m["subject"].lower() for m in inbox)


async def test_both_requesters_are_notified_when_a_shared_request_is_declined(client):
    movie_id = await _create_movie(client, "Delt Afvisning")
    first = await _second_user(client, "sharedfirst")
    second = await _second_user(client, "sharedsecond")

    created = await first.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )
    await second.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-02T20:00:00"},
    )
    request_id = created.json()["id"]

    await client.patch(f"/api/screening-requests/{request_id}", json={"status": "declined"})

    first_inbox = (await first.get("/api/messages/inbox")).json()
    second_inbox = (await second.get("/api/messages/inbox")).json()
    assert any("Delt Afvisning" in m["body"] for m in first_inbox)
    assert any("Delt Afvisning" in m["body"] for m in second_inbox)


async def test_requester_is_notified_when_their_request_is_scheduled(client):
    movie_id = await _create_movie(client, "Planlagt Titel")
    requester = await _second_user(client, "scheduledrequester")

    created = await requester.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )
    request_id = created.json()["id"]

    scheduled = await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "scheduled_at": "2099-09-01T20:00:00",
            "request_id": request_id,
        },
    )
    assert scheduled.status_code == 201

    inbox = (await requester.get("/api/messages/inbox")).json()
    assert any("Planlagt Titel" in m["body"] for m in inbox)
    assert any("planlagt" in m["subject"].lower() for m in inbox)


async def test_requester_is_still_notified_when_notify_scope_is_explicitly_requesters(client):
    """Feature #221 — den eksplicitte "requesters"-værdi opfører sig
    identisk med at udelade feltet helt (default), ikke kun default selv."""
    movie_id = await _create_movie(client, "Eksplicit Anmodningsstiller")
    requester = await _second_user(client, "explicitscoperequester")

    created = await requester.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )
    request_id = created.json()["id"]

    scheduled = await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "scheduled_at": "2099-09-01T20:00:00",
            "request_id": request_id,
            "notify_scope": "requesters",
        },
    )
    assert scheduled.status_code == 201

    inbox = (await requester.get("/api/messages/inbox")).json()
    assert any("Eksplicit Anmodningsstiller" in m["body"] for m in inbox)


async def test_only_the_requester_is_notified_when_notify_scope_is_requesters(client):
    """Feature #221 — en urelateret, aktiv bruger (der hverken ønskede
    titlen eller planlægger den) skal IKKE få besked ved default-scope."""
    movie_id = await _create_movie(client, "Snæver Anmodning")
    requester = await _second_user(client, "narrowscoperequester")
    bystander = await _second_user(client, "narrowscopebystander")

    created = await requester.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )
    request_id = created.json()["id"]

    await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "scheduled_at": "2099-09-01T20:00:00",
            "request_id": request_id,
        },
    )

    bystander_inbox = (await bystander.get("/api/messages/inbox")).json()
    assert not any("Snæver Anmodning" in m["body"] for m in bystander_inbox)


async def test_all_active_users_are_notified_when_notify_scope_is_all(client):
    """Feature #221 (Jan: "en mulighed for at tilvælge om man vil sende
    email notifikation ud til alle eller kun Anmodninger stiller") — en
    urelateret, aktiv bruger skal få besked når admin vælger "all"."""
    movie_id = await _create_movie(client, "Bred Anmodning")
    requester = await _second_user(client, "broadscoperequester")
    bystander = await _second_user(client, "broadscopebystander")

    created = await requester.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )
    request_id = created.json()["id"]

    scheduled = await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "scheduled_at": "2099-09-01T20:00:00",
            "request_id": request_id,
            "notify_scope": "all",
        },
    )
    assert scheduled.status_code == 201

    bystander_inbox = (await bystander.get("/api/messages/inbox")).json()
    assert any("Bred Anmodning" in m["body"] for m in bystander_inbox)


async def test_requester_gets_the_broadcast_not_the_targeted_reply_when_notify_scope_is_all(client):
    """Feature #221 — de to notifikations-veje er gensidigt udelukkende:
    ved "all" får anmodningsstilleren rundsendingen (som alle andre aktive
    brugere), ikke OGSÅ den målrettede #202-svar-besked."""
    movie_id = await _create_movie(client, "Kun Rundsendt")
    requester = await _second_user(client, "onlybroadcastrequester")

    created = await requester.post(
        "/api/screening-requests",
        json={"media_kind": "movie", "movie_id": movie_id, "preferred_at": "2099-09-01T20:00:00"},
    )
    request_id = created.json()["id"]

    await client.post(
        "/api/screenings",
        json={
            "media_kind": "movie",
            "movie_id": movie_id,
            "scheduled_at": "2099-09-01T20:00:00",
            "request_id": request_id,
            "notify_scope": "all",
        },
    )

    inbox = (await requester.get("/api/messages/inbox")).json()
    matching = [m for m in inbox if "Kun Rundsendt" in m["body"]]
    assert len(matching) == 1
    assert matching[0]["subject"] == '"Kun Rundsendt" er planlagt i Voldby BIO!'


async def test_scheduling_without_a_request_id_does_not_notify_anyone(client):
    """Et direkte-tilføjet fremvisning (ingen tilknyttet ønske) har ingen
    ønsker at svare til — skal ikke fejle, og skal ikke sende noget."""
    movie_id = await _create_movie(client, "Direkte Tilføjet")
    requester = await _second_user(client, "unrelateduser")

    response = await client.post(
        "/api/screenings",
        json={"media_kind": "movie", "movie_id": movie_id, "scheduled_at": "2099-09-01T20:00:00"},
    )
    assert response.status_code == 201

    inbox = (await requester.get("/api/messages/inbox")).json()
    assert inbox == []


async def test_admin_is_notified_when_a_user_adds_a_movie_to_the_wishlist(client):
    wisher = await _second_user(client, "moviewisher")
    created = await wisher.post(
        "/api/movies",
        json={"title": "Ønsket Film", "is_wishlist": True},
    )
    assert created.status_code == 201

    inbox = (await client.get("/api/messages/inbox")).json()
    assert any("Ønsket Film" in m["body"] for m in inbox)
    assert any(m["subject"] == "Nyt ønske på indkøbslisten" for m in inbox)


async def test_admin_is_notified_when_a_user_adds_a_tv_show_to_the_wishlist(client):
    wisher = await _second_user(client, "tvwisher")
    created = await wisher.post(
        "/api/tv-shows",
        json={"name": "Ønsket Serie", "is_wishlist": True},
    )
    assert created.status_code == 201

    inbox = (await client.get("/api/messages/inbox")).json()
    assert any("Ønsket Serie" in m["body"] for m in inbox)
    assert any(m["subject"] == "Nyt ønske på indkøbslisten" for m in inbox)


async def test_admin_is_not_notified_for_a_regular_non_wishlist_library_addition(client):
    # Gæster må kun oprette ønsker (enforce_guest_wishlist_only), så en
    # almindelig biblioteks-tilføjelse testes her direkte som admin — pointen
    # er blot at is_wishlist=False aldrig udløser notify_admins_new_wishlist,
    # uafhængigt af hvem der opretter.
    created = await client.post(
        "/api/movies",
        json={"title": "Almindelig Film", "media_type": "Fysisk", "format": "F-DVD"},
    )
    assert created.status_code == 201

    inbox = (await client.get("/api/messages/inbox")).json()
    assert not any(m["subject"] == "Nyt ønske på indkøbslisten" for m in inbox)
