"""Feature #204 — layoutet for de rigere HTML-svar-mails (poster-billede +
inspirerende tekst). Kun ren funktionstest af selve render-funktionen —
det er `test_messages.py` der dækker at message_service rent faktisk
kalder den med de rigtige data for hver af de seks svar-typer."""

from app.integrations import email_templates


def test_render_includes_poster_image_when_given():
    html = email_templates.render_notification_email(
        headline="Dit ønske er godkendt!",
        tagline="Tagline",
        body_text="Body",
        poster_url="https://image.tmdb.org/t/p/w342/abc.jpg",
    )
    assert "https://image.tmdb.org/t/p/w342/abc.jpg" in html
    assert "<img" in html


def test_render_omits_image_block_when_no_poster():
    html = email_templates.render_notification_email(
        headline="Om dit ønske", tagline="Tagline", body_text="Body", poster_url=None
    )
    assert "<img" not in html


def test_render_escapes_html_in_all_text_fields():
    """Filmtitler kan være frit indtastet (manuel oprettelse), og en admins
    afvisnings-begrundelse er fri tekst — begge ender i tagline/body_text.
    Uden escaping kunne en titel med `<script>` injicere markup i mailen."""
    html = email_templates.render_notification_email(
        headline="<script>alert('h')</script>",
        tagline="<script>alert('t')</script>",
        body_text="<script>alert('b')</script>",
        poster_url="javascript:alert('p')",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_converts_newlines_in_body_to_line_breaks():
    html = email_templates.render_notification_email(
        headline="H", tagline="T", body_text="Første linje\n\nAnden linje", poster_url=None
    )
    assert "Første linje<br><br>Anden linje" in html


def test_render_uses_muted_accent_for_rejection_tone():
    gold = email_templates.render_notification_email(
        headline="H", tagline="T", body_text="B", accent="gold"
    )
    muted = email_templates.render_notification_email(
        headline="H", tagline="T", body_text="B", accent="muted"
    )
    assert gold != muted
