"""Feature #222 (Jan: "hvis nye film/tv bliver adderet til database så
bliver der sendt en besked til alle at der er kommet en ny fede film/tv til
samlingen og at man nu kan anmode om bio tid ... lave også et flueben
setting i forbindelse med der hvor man addere film/tv om hvor vidt man vil
sende besked til alle eller ikke") — valgfri broadcast-besked til alle
aktive brugere ved en rigtig (ikke-ønske) biblioteks-tilføjelse, eller når
et ønske flyttes til biblioteket. Styret af `notify_all` på selve
oprettelses-/opdaterings-kaldet, aldrig gemt på dokumentet.
"""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _member(admin_client, name):
    transport = ASGITransport(app=app)
    member = AsyncClient(transport=transport, base_url="http://test")
    register = await member.post(
        "/api/auth/register", json={"username": name, "password": "testpassword123"}
    )
    await admin_client.patch(
        f"/api/users/{register.json()['id']}/status", json={"status": "active"}
    )
    return member


async def test_creating_a_movie_with_notify_all_broadcasts_to_another_user(client):
    bystander = await _member(client, "movie_bystander")

    created = await client.post(
        "/api/movies",
        json={
            "title": "Broadcast Film",
            "media_type": "Fysisk",
            "format": "F-DVD",
            "notify_all": True,
        },
    )
    assert created.status_code == 201

    inbox = (await bystander.get("/api/messages/inbox")).json()
    assert any("Broadcast Film" in m["body"] for m in inbox)
    await bystander.aclose()


async def test_creating_a_movie_without_notify_all_sends_nothing(client):
    bystander = await _member(client, "movie_no_broadcast_bystander")

    created = await client.post(
        "/api/movies",
        json={"title": "Stille Film", "media_type": "Fysisk", "format": "F-DVD"},
    )
    assert created.status_code == 201

    inbox = (await bystander.get("/api/messages/inbox")).json()
    assert not any("Stille Film" in m["body"] for m in inbox)
    await bystander.aclose()


async def test_creating_a_wishlist_movie_with_notify_all_does_not_broadcast(client):
    """`notify_all` er kun relevant for en RIGTIG biblioteks-tilføjelse —
    et ønske har jo ikke ramt samlingen endnu."""
    bystander = await _member(client, "wishlist_no_broadcast_bystander")

    created = await client.post(
        "/api/movies",
        json={"title": "Ønske Film", "is_wishlist": True, "notify_all": True},
    )
    assert created.status_code == 201

    inbox = (await bystander.get("/api/messages/inbox")).json()
    assert not any("Ønske Film" in m["body"] for m in inbox)
    await bystander.aclose()


async def test_creating_a_tv_show_with_notify_all_broadcasts_to_another_user(client):
    bystander = await _member(client, "tv_bystander")

    created = await client.post(
        "/api/tv-shows",
        json={
            "name": "Broadcast Serie",
            "media_type": "Fysisk",
            "format": "F-DVD",
            "notify_all": True,
        },
    )
    assert created.status_code == 201

    inbox = (await bystander.get("/api/messages/inbox")).json()
    assert any("Broadcast Serie" in m["body"] for m in inbox)
    await bystander.aclose()


async def test_creator_does_not_receive_their_own_broadcast(client):
    """Rundsendingen udelader afsenderen selv, samme mekanisme som #221s
    notify_screening_scheduled_broadcast (send()s egen sender-udelukkelse)."""
    created = await client.post(
        "/api/movies",
        json={
            "title": "Egen Broadcast Film",
            "media_type": "Fysisk",
            "format": "F-DVD",
            "notify_all": True,
        },
    )
    assert created.status_code == 201

    inbox = (await client.get("/api/messages/inbox")).json()
    assert not any("Egen Broadcast Film" in m["body"] for m in inbox)


async def test_broadcast_message_links_to_the_public_site(client):
    bystander = await _member(client, "movie_link_bystander")

    await client.post(
        "/api/movies",
        json={
            "title": "Link Film",
            "media_type": "Fysisk",
            "format": "F-DVD",
            "notify_all": True,
        },
    )

    inbox = (await bystander.get("/api/messages/inbox")).json()
    match = next(m for m in inbox if "Link Film" in m["body"])
    assert "movie.laces.dk" in match["body"]
    await bystander.aclose()


async def test_moving_a_wishlist_movie_to_library_with_notify_all_also_broadcasts(client):
    """Feature #222 — begge veje (Jans valg): "Flyt til bibliotek" udløser
    BÅDE den eksisterende personlige besked til ønskeren (#141) OG, hvis
    fluebenet er sat, en broadcast til alle andre aktive brugere."""
    wisher = await _member(client, "move_wisher")
    bystander = await _member(client, "move_bystander")

    created = await wisher.post(
        "/api/movies", json={"title": "Flyttet Film", "is_wishlist": True}
    )
    movie_id = created.json()["id"]

    resp = await client.patch(
        f"/api/movies/{movie_id}",
        json={
            "is_wishlist": False,
            "media_type": "Fysisk",
            "format": "F-DVD",
            "notify_all": True,
        },
    )
    assert resp.status_code == 200

    wisher_inbox = (await wisher.get("/api/messages/inbox")).json()
    assert any("Flyttet Film" in m["body"] for m in wisher_inbox)

    bystander_inbox = (await bystander.get("/api/messages/inbox")).json()
    assert any("Flyttet Film" in m["body"] for m in bystander_inbox)

    await wisher.aclose()
    await bystander.aclose()


async def test_moving_a_wishlist_movie_to_library_without_notify_all_only_notifies_wisher(client):
    wisher = await _member(client, "move_no_broadcast_wisher")
    bystander = await _member(client, "move_no_broadcast_bystander")

    created = await wisher.post(
        "/api/movies", json={"title": "Stille Flyttet Film", "is_wishlist": True}
    )
    movie_id = created.json()["id"]

    resp = await client.patch(
        f"/api/movies/{movie_id}",
        json={"is_wishlist": False, "media_type": "Fysisk", "format": "F-DVD"},
    )
    assert resp.status_code == 200

    wisher_inbox = (await wisher.get("/api/messages/inbox")).json()
    assert any("Stille Flyttet Film" in m["body"] for m in wisher_inbox)

    bystander_inbox = (await bystander.get("/api/messages/inbox")).json()
    assert not any("Stille Flyttet Film" in m["body"] for m in bystander_inbox)

    await wisher.aclose()
    await bystander.aclose()


async def test_a_non_admin_standard_user_can_also_trigger_the_broadcast(client):
    """Jans eksplicitte valg: fluebenet er ikke admin-only — enhver rolle
    der kan tilføje en rigtig biblioteks-post kan også vælge at annoncere
    den til alle. Ny brugere er guest som default (feature #72) og må kun
    tilføje til ønskelisten, så denne bruger forfremmes eksplicit til
    "standard" — den laveste rolle der overhovedet må tilføje til
    biblioteket (ikke admin)."""
    transport = ASGITransport(app=app)
    standard = AsyncClient(transport=transport, base_url="http://test")
    register = await standard.post(
        "/api/auth/register", json={"username": "standard_broadcaster", "password": "testpassword123"}
    )
    await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})
    await client.patch(f"/api/users/{register.json()['id']}/role", json={"role": "standard"})
    bystander = await _member(client, "standard_broadcast_bystander")

    created = await standard.post(
        "/api/movies",
        json={
            "title": "Standard Bruger Film",
            "media_type": "Fysisk",
            "format": "F-DVD",
            "notify_all": True,
        },
    )
    assert created.status_code == 201

    inbox = (await bystander.get("/api/messages/inbox")).json()
    assert any("Standard Bruger Film" in m["body"] for m in inbox)
    await standard.aclose()
    await bystander.aclose()
