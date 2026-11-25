"""Feature #232 — den samlede opdatering (og "send med det samme") viser ALLE
titler i mailen: plakat-collage + et kort pr. titel, i stedet for kun den
første plakat og en navneliste. Portal-beskeden får titlerne med som
`media`, og køen kan forhåndsvises før afsendelse."""

from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.integrations import email_client, email_templates
from app.main import app

POSTER = "https://image.tmdb.org/t/p/w500/{}.jpg"


async def _member(admin_client, name, role=None, email=None):
    transport = ASGITransport(app=app)
    member = AsyncClient(transport=transport, base_url="http://test")
    register = await member.post(
        "/api/auth/register", json={"username": name, "password": "testpassword123"}
    )
    user_id = register.json()["id"]
    await admin_client.patch(f"/api/users/{user_id}/status", json={"status": "active"})
    if role:
        await admin_client.patch(f"/api/users/{user_id}/role", json={"role": role})
    if email:
        await admin_client.patch(f"/api/users/{user_id}/email", json={"email": email})
    return member


async def _movie(client, title, announce="queue", **extra):
    payload = {"title": title, "media_type": "Fysisk", "format": "F-DVD", "announce": announce, **extra}
    response = await client.post("/api/movies", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _show(client, name, announce="queue", **extra):
    payload = {"name": name, "media_type": "Fysisk", "format": "F-DVD", "announce": announce, **extra}
    response = await client.post("/api/tv-shows", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _capture_emails(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "email_from_address", "Voldby BIO <noreply@laces.dk>")
    sent = []

    async def fake_send_email(to, subject, text, html=None):
        sent.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    monkeypatch.setattr(email_client, "send_email", fake_send_email)
    return sent


# --- Rene layout-funktioner -------------------------------------------------


def test_sized_poster_rewrites_only_tmdb_urls():
    assert email_templates.sized_poster(POSTER.format("abc"), "w185") == "https://image.tmdb.org/t/p/w185/abc.jpg"
    assert email_templates.sized_poster("https://example.com/p.jpg", "w185") == "https://example.com/p.jpg"
    assert email_templates.sized_poster(None, "w185") is None
    assert email_templates.sized_poster("   ", "w185") is None


def test_shorten_cuts_at_a_word_and_treats_whitespace_as_empty():
    assert email_templates.shorten("   \n ") == ""
    assert email_templates.shorten(None) == ""
    long_text = "ord " * 100
    short = email_templates.shorten(long_text, 30)
    assert short.endswith("…")
    assert len(short) <= 31
    assert "or…" not in short  # aldrig midt i et ord


def test_zero_rating_is_not_shown_but_a_real_one_is():
    assert email_templates.rating_text(0.0) is None
    assert email_templates.rating_text(None) is None
    assert email_templates.rating_text("ikke et tal") is None
    assert email_templates.rating_text(7.84) == "7,8"


def test_showcase_escapes_user_text():
    html = email_templates.render_showcase_email(
        headline="<b>Hej</b>",
        tagline="t",
        items=[
            {"title": "<script>x</script>", "media_kind": "movie", "overview": "<img onerror=1>"},
            {"title": "B", "media_kind": "tv", "genres": ["<i>g</i>"]},
        ],
    )
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img onerror" not in html
    assert "<b>Hej</b>" not in html
    assert "<i>g</i>" not in html


def test_collage_caps_at_twelve_tiles_with_a_more_tile():
    items = [
        {"title": f"T{i}", "media_kind": "movie", "poster_url": POSTER.format(f"p{i}")} for i in range(15)
    ]
    html = email_templates.render_showcase_email(headline="h", tagline="t", items=items)
    # 11 plakater i collagen (w342) + "+4"-feltet; alle 15 har stadig et kort (w185).
    assert html.count("/w342/") == 11
    assert "+4" in html
    assert html.count("/w185/") == 15


def test_single_title_has_no_collage_and_no_counter():
    html = email_templates.render_showcase_email(
        headline="h", tagline="t", items=[{"title": "Solo", "media_kind": "movie", "poster_url": POSTER.format("s")}]
    )
    assert "/w342/" not in html
    assert "1 film" not in html


# --- Den rigtige afsendelse ------------------------------------------------


async def test_digest_email_shows_every_title_with_its_details(client, monkeypatch):
    sent = _capture_emails(monkeypatch)
    bystander = await _member(client, "sc_bystander", email="sc@example.com")
    await _movie(
        client,
        "Første Film",
        year=2024,
        poster_url=POSTER.format("first"),
        genres=["Drama", "Krimi"],
        overview="En historie om noget.",
    )
    await _show(client, "Anden Serie", year=2022, poster_url=POSTER.format("second"))
    await _movie(client, "Tredje Film")

    assert (await client.post("/api/announcements/send")).status_code == 200

    assert len(sent) == 1
    html = sent[0]["html"]
    for title in ("Første Film", "Anden Serie", "Tredje Film"):
        assert title in html
    # Begge plakater er med — ikke kun den første.
    assert "first.jpg" in html and "second.jpg" in html
    assert "Drama · Krimi" in html
    assert "En historie om noget." in html
    assert "SERIE" in html and "FILM" in html
    assert "2 film" in html and "1 serie" in html
    # Tekst-alternativet og portal-beskeden har året med.
    assert "• Første Film (2024, film)" in sent[0]["text"]
    await bystander.aclose()


async def test_portal_message_carries_the_titles_as_media(client):
    bystander = await _member(client, "media_bystander")
    await _movie(client, "Media Film", year=2020, poster_url=POSTER.format("m"))
    await _show(client, "Media Serie")
    await client.post("/api/announcements/send")

    inbox = (await bystander.get("/api/messages/inbox")).json()
    assert inbox[0]["media"] == [
        {"title": "Media Film", "media_kind": "movie", "year": 2020, "poster_url": POSTER.format("m")},
        {"title": "Media Serie", "media_kind": "tv", "year": None, "poster_url": None},
    ]
    await bystander.aclose()


async def test_ordinary_messages_have_no_media(client):
    member = await _member(client, "plain_member")
    await client.post("/api/messages", json={"subject": "Hej", "body": "Krop"})
    inbox = (await member.get("/api/messages/inbox")).json()
    assert inbox and all(message["media"] == [] for message in inbox)
    await member.aclose()


async def test_now_mode_email_uses_the_card_layout(client, monkeypatch):
    sent = _capture_emails(monkeypatch)
    bystander = await _member(client, "now_sc", email="now@example.com")
    await _movie(client, "Straks", announce="now", year=1999, overview="Resumé her.", poster_url=POSTER.format("n"))

    assert len(sent) == 1
    assert "Resumé her." in sent[0]["html"]
    assert "(1999)" in sent[0]["html"]
    assert "/w185/n.jpg" in sent[0]["html"]
    inbox = (await bystander.get("/api/messages/inbox")).json()
    assert inbox[0]["media"][0]["title"] == "Straks"
    await bystander.aclose()


async def test_a_very_long_queue_still_sends_with_a_shortened_text_list(client, monkeypatch):
    """Før #232 gav en brødtekst over 2000 tegn en valideringsfejl, og hele
    afsendelsen fejlede."""
    sent = _capture_emails(monkeypatch)
    bystander = await _member(client, "long_bystander", email="long@example.com")
    for i in range(70):
        await _movie(client, f"En ret lang filmtitel nummer {i:02d} til test")

    response = await client.post("/api/announcements/send")
    assert response.status_code == 200, response.text
    assert response.json() == {"sent_count": 70}

    inbox = (await bystander.get("/api/messages/inbox")).json()
    body = inbox[0]["body"]
    assert len(body) <= 2000
    assert "… og " in body and " mere" in body
    # Mailen har stadig et kort for hver eneste titel.
    assert sent[0]["html"].count("En ret lang filmtitel nummer") >= 70
    assert len(inbox[0]["media"]) == 70
    await bystander.aclose()


# --- Forhåndsvisning --------------------------------------------------------


async def test_preview_matches_what_is_sent_and_sends_nothing(client, monkeypatch):
    sent = _capture_emails(monkeypatch)
    bystander = await _member(client, "pv_bystander", email="pv@example.com")
    await _movie(client, "Preview Film", year=2001)

    response = await client.get("/api/announcements/preview")
    assert response.status_code == 200
    preview = response.json()
    assert preview["count"] == 1
    assert preview["subject"] == "Nyt i Voldby BIO-samlingen"
    assert "Preview Film" in preview["html"]
    assert "• Preview Film (2001, film)" in preview["body"]

    # Intet sendt, køen urørt.
    assert sent == []
    assert (await bystander.get("/api/messages/inbox")).json() == []
    assert len((await client.get("/api/announcements")).json()) == 1

    await client.post("/api/announcements/send")
    assert sent[0]["html"] == preview["html"]
    assert sent[0]["subject"] == preview["subject"]
    await bystander.aclose()


async def test_preview_uses_customized_wording(client):
    response = await client.patch(
        "/api/messages/templates/library_additions_digest",
        json={"headline": "Fredagens nye fund"},
    )
    assert response.status_code == 200, response.text
    await _movie(client, "Tilpasset")
    preview = (await client.get("/api/announcements/preview")).json()
    assert "Fredagens nye fund" in preview["html"]


async def test_preview_of_an_empty_queue_is_409(client):
    assert (await client.get("/api/announcements/preview")).status_code == 409


async def test_guests_cannot_preview(client):
    await _movie(client, "Gæst Må Ikke")
    guest = await _member(client, "pv_guest", role="guest")
    assert (await guest.get("/api/announcements/preview")).status_code == 403
    await guest.aclose()


async def test_queue_rows_include_the_year(client):
    await _movie(client, "Med År", year=1984)
    queue = (await client.get("/api/announcements")).json()
    assert queue[0]["year"] == 1984
