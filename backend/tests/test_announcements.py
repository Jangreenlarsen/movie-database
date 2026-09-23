"""Feature #228 — "Samlet opdatering". Nye titler kan lægges i en fælles kø
i stedet for at udløse én besked pr. titel (#222); en admin/standardbruger
sender så hele køen som én besked til alle.
"""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _member(admin_client, name, role=None):
    transport = ASGITransport(app=app)
    member = AsyncClient(transport=transport, base_url="http://test")
    register = await member.post(
        "/api/auth/register", json={"username": name, "password": "testpassword123"}
    )
    user_id = register.json()["id"]
    await admin_client.patch(f"/api/users/{user_id}/status", json={"status": "active"})
    if role:
        await admin_client.patch(f"/api/users/{user_id}/role", json={"role": role})
    return member


async def _movie(client, title, announce=None, **extra):
    payload = {"title": title, "media_type": "Fysisk", "format": "F-DVD", **extra}
    if announce is not None:
        payload["announce"] = announce
    response = await client.post("/api/movies", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _show(client, name, announce=None, **extra):
    payload = {"name": name, "media_type": "Fysisk", "format": "F-DVD", **extra}
    if announce is not None:
        payload["announce"] = announce
    response = await client.post("/api/tv-shows", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_queue_mode_adds_to_queue_and_sends_nothing_yet(client):
    bystander = await _member(client, "q_bystander")
    await _movie(client, "Kø Film", announce="queue")

    queue = (await client.get("/api/announcements")).json()
    assert [(q["media_kind"], q["title"], q["added_by"]) for q in queue] == [
        ("movie", "Kø Film", "testuser")
    ]
    assert (await bystander.get("/api/messages/inbox")).json() == []
    await bystander.aclose()


async def test_sending_the_queue_is_one_message_listing_every_title(client):
    bystander = await _member(client, "digest_bystander")
    await _movie(client, "Første Film", announce="queue")
    await _show(client, "Anden Serie", announce="queue")
    await _movie(client, "Tredje Film", announce="queue")

    response = await client.post("/api/announcements/send")
    assert response.status_code == 200
    assert response.json() == {"sent_count": 3}

    inbox = (await bystander.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    body = inbox[0]["body"]
    assert inbox[0]["subject"] == "Nyt i Voldby BIO-samlingen"
    assert "• Første Film (film)\n• Anden Serie (serie)\n• Tredje Film (film)" in body
    assert (await client.get("/api/announcements")).json() == []
    await bystander.aclose()


async def test_now_mode_still_broadcasts_immediately_and_skips_the_queue(client):
    bystander = await _member(client, "now_bystander")
    await _movie(client, "Straks Film", announce="now")

    inbox = (await bystander.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    assert "Straks Film" in inbox[0]["subject"]
    assert (await client.get("/api/announcements")).json() == []
    await bystander.aclose()


async def test_none_mode_does_nothing(client):
    bystander = await _member(client, "none_bystander")
    await _movie(client, "Stille Film", announce="none")

    assert (await client.get("/api/announcements")).json() == []
    assert (await bystander.get("/api/messages/inbox")).json() == []
    await bystander.aclose()


async def test_legacy_notify_all_still_means_now(client):
    """En klient der kun kender #222's `notify_all` opfører sig som før."""
    bystander = await _member(client, "legacy_bystander")
    await _movie(client, "Gammel Klient Film", notify_all=True)

    assert len((await bystander.get("/api/messages/inbox")).json()) == 1
    assert (await client.get("/api/announcements")).json() == []
    await bystander.aclose()


async def test_wishlist_items_are_never_queued(client):
    await _movie(client, "Ønske Film", announce="queue", is_wishlist=True)
    assert (await client.get("/api/announcements")).json() == []


async def test_moving_a_wish_to_the_library_can_queue_it(client):
    wish = await _movie(client, "Flyttet Ønske", is_wishlist=True)
    response = await client.patch(
        f"/api/movies/{wish['id']}", json={"is_wishlist": False, "announce": "queue"}
    )
    assert response.status_code == 200, response.text

    queue = (await client.get("/api/announcements")).json()
    assert [q["title"] for q in queue] == ["Flyttet Ønske"]


async def test_moving_a_tv_wish_to_the_library_can_queue_it(client):
    wish = await _show(client, "Flyttet Serieønske", is_wishlist=True)
    response = await client.patch(
        f"/api/tv-shows/{wish['id']}", json={"is_wishlist": False, "announce": "queue"}
    )
    assert response.status_code == 200, response.text

    queue = (await client.get("/api/announcements")).json()
    assert [(q["media_kind"], q["title"]) for q in queue] == [("tv", "Flyttet Serieønske")]


async def test_the_same_title_is_never_queued_twice(client):
    wish = await _movie(client, "Dobbelt", is_wishlist=True)
    await client.patch(f"/api/movies/{wish['id']}", json={"is_wishlist": False, "announce": "queue"})
    # Tilbage på ønskelisten og ind igen — stadig kun én post.
    await client.patch(f"/api/movies/{wish['id']}", json={"is_wishlist": True})
    await client.patch(f"/api/movies/{wish['id']}", json={"is_wishlist": False, "announce": "queue"})

    assert len((await client.get("/api/announcements")).json()) == 1


async def test_deleted_titles_drop_out_of_the_queue(client):
    kept = await _movie(client, "Bliver", announce="queue")
    gone = await _movie(client, "Slettes", announce="queue")
    await client.delete(f"/api/movies/{gone['id']}")

    queue = (await client.get("/api/announcements")).json()
    assert [q["item_id"] for q in queue] == [kept["id"]]


async def test_titles_moved_back_to_the_wishlist_drop_out(client):
    movie = await _movie(client, "Fortrudt", announce="queue")
    await client.patch(f"/api/movies/{movie['id']}", json={"is_wishlist": True})

    assert (await client.get("/api/announcements")).json() == []


async def test_queue_shows_the_current_title_not_the_one_at_queue_time(client):
    movie = await _movie(client, "Stavefjel", announce="queue")
    await client.patch(f"/api/movies/{movie['id']}", json={"title": "Stavefejl"})

    assert [q["title"] for q in (await client.get("/api/announcements")).json()] == ["Stavefejl"]


async def test_removing_one_title_leaves_the_rest(client):
    await _movie(client, "Fjernes", announce="queue")
    await _movie(client, "Bliver Stående", announce="queue")
    queue = (await client.get("/api/announcements")).json()

    response = await client.delete(f"/api/announcements/{queue[0]['id']}")
    assert response.status_code == 204
    assert [q["title"] for q in (await client.get("/api/announcements")).json()] == [
        "Bliver Stående"
    ]
    # Selve filmen er urørt.
    assert (await client.get(f"/api/movies/{queue[0]['item_id']}")).status_code == 200


async def test_removing_an_unknown_entry_is_404(client):
    response = await client.delete("/api/announcements/000000000000000000000000")
    assert response.status_code == 404


async def test_sending_an_empty_queue_is_409(client):
    response = await client.post("/api/announcements/send")
    assert response.status_code == 409
    assert "ingen titler" in response.json()["detail"]


async def test_standard_user_can_queue_see_and_send(client):
    standard = await _member(client, "std_announcer", role="standard")
    bystander = await _member(client, "std_bystander")
    await _movie(standard, "Standard Film", announce="queue")

    queue = (await standard.get("/api/announcements")).json()
    assert [q["added_by"] for q in queue] == ["std_announcer"]
    response = await standard.post("/api/announcements/send")
    assert response.status_code == 200

    inbox = (await bystander.get("/api/messages/inbox")).json()
    assert len(inbox) == 1
    assert inbox[0]["sent_by"] == "std_announcer"
    await standard.aclose()
    await bystander.aclose()


async def test_queue_is_shared_across_users(client):
    """Én fælles kø (Jans valg): admins titel og standardbrugerens står
    sammen, og hvem som helst af dem sender det hele."""
    standard = await _member(client, "std_shared", role="standard")
    await _movie(client, "Admins Film", announce="queue")
    await _movie(standard, "Standards Film", announce="queue")

    queue = (await standard.get("/api/announcements")).json()
    assert [q["title"] for q in queue] == ["Admins Film", "Standards Film"]
    assert (await standard.post("/api/announcements/send")).json() == {"sent_count": 2}
    await standard.aclose()


async def test_guests_cannot_see_or_send_the_queue(client):
    guest = await _member(client, "guest_announcer", role="guest")
    await _movie(client, "Gæst Ser Ikke", announce="queue")

    assert (await guest.get("/api/announcements")).status_code == 403
    assert (await guest.post("/api/announcements/send")).status_code == 403
    queue = (await client.get("/api/announcements")).json()
    assert (await guest.delete(f"/api/announcements/{queue[0]['id']}")).status_code == 403
    assert len((await client.get("/api/announcements")).json()) == 1
    await guest.aclose()


async def test_test_mode_blocks_sending_and_keeps_the_queue(client):
    """#217 — test-tilstand må ikke sende, og køen må ikke tømmes for noget
    der aldrig gik ud."""
    bystander = await _member(client, "tm_bystander")
    await _movie(client, "Test Tilstand Film", announce="queue")
    await client.patch("/api/settings/test-mode", json={"test_mode": True})

    response = await client.post("/api/announcements/send")
    assert response.status_code == 409
    assert len((await client.get("/api/announcements")).json()) == 1
    assert (await bystander.get("/api/messages/inbox")).json() == []

    await client.patch("/api/settings/test-mode", json={"test_mode": False})
    await bystander.aclose()


async def test_system_backup_round_trip_keeps_the_queue(client):
    """Regel 20 — køen er med i system-backup og kommer tilbage ved restore."""
    await _movie(client, "Backup Kø Film", announce="queue")
    backup = (await client.get("/api/system/backup")).json()
    assert len(backup["pending_announcements"]) == 1

    queue = (await client.get("/api/announcements")).json()
    await client.delete(f"/api/announcements/{queue[0]['id']}")
    assert (await client.get("/api/announcements")).json() == []

    restored = await client.post("/api/system/restore", json=backup)
    assert restored.status_code == 200, restored.text
    assert restored.json()["pending_announcements_imported"] == 1
    assert [q["title"] for q in (await client.get("/api/announcements")).json()] == [
        "Backup Kø Film"
    ]


async def test_library_reset_clears_the_queue(client):
    await _movie(client, "Reset Kø Film", announce="queue")
    response = await client.post(
        "/api/system/reset", json={"current_password": "testpassword123"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["pending_announcements_removed"] == 1
    assert (await client.get("/api/announcements")).json() == []
