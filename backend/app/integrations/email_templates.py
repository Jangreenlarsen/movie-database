"""Feature #204 — layout for de "svar"-mails en bruger får når admin
reagerer på et ønske eller en forvisnings-anmodning (godkendt/afvist/
bestilt/flyttet/planlagt/afvist forvisning). Kun LAYOUT bor her — selve
teksten (headline/tagline/brødtekst pr. begivenhed) skrives af
message_service, som kender den faktiske forretningskontekst.

Tabel-baseret opmarkering, udelukkende inline styles — e-mail-klienter
(især Outlook desktop, som render'er med Words motor) understøtter langt
fra moderne CSS, og eksterne stylesheets/klasser virker slet ikke pålideligt.
Poster-billedet er den ENESTE eksterne billed-reference (TMDb's egen,
altid absolutte URL) — bevidst INGEN hardkodet logo-billede fra appens eget
domæne, da appen kan selvhostes på et vilkårligt domæne (DEPLOYMENT.md
#152, "genanvendelig appliance-skabelon")."""

import html as html_lib
import re

_ACCENT = {
    # Fest-farven — godkendt/bestilt/flyttet/planlagt. Samme rav-toner som
    # den eksisterende .movie-order-badge på ønske-kortet (Library.css),
    # så mailen visuelt matcher appens egen "bestilt"-farve.
    "gold": "#d97706",
    # Dæmpet — afvist-typer. Ikke alarmerende rød (det er ikke en fejl,
    # bare et nej), men tydeligt IKKE fest-tonen.
    "muted": "#78716c",
}


def render_notification_email(
    *,
    headline: str,
    tagline: str,
    body_text: str,
    poster_url: str | None = None,
    accent: str = "gold",
    cta_url: str | None = None,
    cta_label: str | None = None,
) -> str:
    """Alle tekst-argumenter er brugerdata (filmtitler kan være frit
    indtastet ved manuel oprettelse, admins afvisnings-begrundelse er fri
    tekst) og escapes derfor eksplicit — uden det ville en titel/begrundelse
    med `<`/`>` kunne injicere markup i mailen (samme klasse sårbarhed som
    reflekteret XSS, blot i en e-mail-klients HTML-renderer i stedet for en
    browser).

    Feature #205 — `cta_url`/`cta_label` er en valgfri knap (bruges af
    password-reset-mailen). `cta_url` forventes allerede valideret af
    kalderen (auth_service — matchet mod settings.cors_origin_list), men
    escapes alligevel her som forsvar-i-dybden, samme princip som
    `poster_url`."""
    accent_color = _ACCENT.get(accent, _ACCENT["gold"])
    safe_headline = html_lib.escape(headline)
    safe_tagline = html_lib.escape(tagline)
    safe_body = html_lib.escape(body_text).replace("\n", "<br>")
    safe_poster = html_lib.escape(poster_url) if poster_url else None

    poster_block = ""
    if safe_poster:
        poster_block = f"""
            <tr>
              <td style="padding:28px 32px 24px;" align="center">
                <img src="{safe_poster}" alt="" width="140"
                     style="display:block;border-radius:10px;box-shadow:0 6px 18px rgba(0,0,0,0.35);" />
              </td>
            </tr>"""
    else:
        poster_block = """
            <tr>
              <td style="padding:28px 32px 0;"></td>
            </tr>"""

    cta_block = ""
    if cta_url and cta_label:
        safe_cta_url = html_lib.escape(cta_url)
        safe_cta_label = html_lib.escape(cta_label)
        cta_block = f"""
            <tr>
              <td style="padding:4px 32px 28px;" align="center">
                <a href="{safe_cta_url}"
                   style="display:inline-block;background:{accent_color};color:#fff;font-weight:700;font-size:14px;text-decoration:none;padding:12px 28px;border-radius:999px;">{safe_cta_label}</a>
              </td>
            </tr>"""

    return f"""<!doctype html>
<html lang="da">
  <body style="margin:0;padding:0;background:#faf9f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#faf9f7;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
            <tr>
              <td style="background:#1c1917;padding:22px 32px;" align="center">
                <span style="color:{accent_color};font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">&#127916; Voldby BIO &middot; Filmportalen</span>
              </td>
            </tr>{poster_block}
            <tr>
              <td style="padding:0 32px 4px;" align="center">
                <h1 style="margin:0;font-size:21px;line-height:1.3;color:#1c1917;">{safe_headline}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 32px 20px;" align="center">
                <p style="margin:0;font-size:15px;color:{accent_color};font-weight:600;">{safe_tagline}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:0 32px 28px;">
                <p style="margin:0;font-size:14px;line-height:1.6;color:#44403c;">{safe_body}</p>
              </td>
            </tr>{cta_block}
            <tr>
              <td style="padding:16px 32px;background:#f5f4f2;border-top:1px solid #e7e5e4;" align="center">
                <p style="margin:0;font-size:11px;color:#a8a29e;">Denne mail er sendt fordi du har en e-mail registreret på din konto i Filmportalen.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


# ---------------------------------------------------------------------------
# Feature #232 — "showcase"-layoutet til nye titler i samlingen: den samlede
# opdatering (#228) og "send med det samme" (#222). Til forskel fra
# `render_notification_email` ovenfor (ét billede, én tekst) viser det ALLE
# titler: en plakat-collage øverst og et kort pr. titel med år, type,
# genrer, bedømmelse og et kort resumé.
#
# Collagen er bevidst en HTML-tabel og ikke ét sammensat billede: et
# genereret billede skulle gemmes og serveres fra en offentlig URL (appen
# kan selvhostes på et vilkårligt domæne, se modul-docstringen), mens en
# tabel med TMDb's egne absolutte plakat-URL'er virker i alle mail-klienter.
# ---------------------------------------------------------------------------

# Farve pr. type — film i biografens rav, serier i en kølig petrol, så man
# kan skelne dem i et blik både i collagen og på kortene.
_KIND_STYLE = {
    "movie": {"label": "FILM", "color": "#f59e0b", "soft": "#fef3c7", "ink": "#92400e"},
    "tv": {"label": "SERIE", "color": "#14b8a6", "soft": "#ccfbf1", "ink": "#115e59"},
}

# Baggrunde til collage-felter uden plakat — så et manglende billede stadig
# bidrager med farve frem for et gråt hul.
_TILE_COLORS = ["#7c2d12", "#134e4a", "#4c1d95", "#831843", "#1e3a8a", "#365314"]

COLLAGE_COLUMNS = 3
COLLAGE_MAX_TILES = 12
OVERVIEW_MAX_CHARS = 180

_TMDB_SIZED = re.compile(r"^(https://image\.tmdb\.org/t/p/)(?:w\d+|original)(/[^/?#]+)$")


def sized_poster(url: str | None, size: str) -> str | None:
    """Plakater gemmes som TMDb's w500-URL. En mail med tolv af dem ville
    hente flere MB, så en TMDb-URL skrives om til en mindre størrelse.
    Andre URL'er (manuelt indtastet, data-URI'en i previewet) bruges
    uændret — vi kender ikke deres størrelses-skema."""
    if not url or not url.strip():
        return None
    match = _TMDB_SIZED.match(url)
    if match is None:
        return url
    return f"{match.group(1)}{size}{match.group(2)}"


def shorten(text: str | None, limit: int = OVERVIEW_MAX_CHARS) -> str:
    """Forkorter ved et ordskifte og tilføjer "…". Tom/whitespace-only
    tekst giver tom streng (regel 16 — alle former for "tom")."""
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    cut = clean[:limit].rsplit(" ", 1)[0].rstrip(",.;:-–— ")
    return f"{cut or clean[:limit]}…"


def _kind(item: dict) -> dict:
    return _KIND_STYLE.get(item.get("media_kind"), _KIND_STYLE["movie"])


def rating_text(rating) -> str | None:
    """TMDb giver 0.0 for en titel uden stemmer — det er "ingen bedømmelse",
    ikke en dårlig film, så den vises ikke. `None` tjekkes eksplicit."""
    if rating is None:
        return None
    try:
        value = float(rating)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return f"{value:.1f}".replace(".", ",")


def _collage(items: list[dict]) -> str:
    tiles = items[:COLLAGE_MAX_TILES]
    extra = len(items) - len(tiles)
    if extra > 0:
        # Sidste felt bliver til "+N flere" i stedet for en plakat, så
        # collagen aldrig vokser ud over fire rækker.
        tiles = tiles[:-1]
        extra += 1
    cells: list[str] = []
    for index, item in enumerate(tiles):
        poster = sized_poster(item.get("poster_url"), "w342")
        title = html_lib.escape(item.get("title") or "")
        color = _kind(item)["color"]
        if poster:
            inner = (
                f'<img src="{html_lib.escape(poster)}" alt="{title}" width="168" '
                f'style="display:block;width:100%;max-width:168px;height:auto;border:0;'
                f'border-radius:8px;border-bottom:3px solid {color};" />'
            )
        else:
            bg = _TILE_COLORS[index % len(_TILE_COLORS)]
            inner = (
                f'<div style="background:{bg};border-radius:8px;border-bottom:3px solid {color};'
                # 2:3 som en rigtig plakat ved fuld bredde (168 × 252).
                f"height:144px;padding:96px 12px 12px;color:#fff;font-size:14px;font-weight:700;"
                f'line-height:1.3;text-align:center;">{title}</div>'
            )
        cells.append(f'<td width="33%" valign="top" style="padding:5px;">{inner}</td>')
    if extra > 0:
        cells.append(
            '<td width="33%" valign="middle" align="center" style="padding:5px;">'
            '<div style="background:#292524;border:2px dashed #57534e;border-radius:8px;height:248px;'
            'color:#fbbf24;font-size:26px;font-weight:800;line-height:248px;text-align:center;">'
            f"+{extra}</div></td>"
        )
    while len(cells) % COLLAGE_COLUMNS:
        cells.append('<td width="33%" style="padding:5px;"></td>')
    rows = "".join(
        "<tr>" + "".join(cells[i : i + COLLAGE_COLUMNS]) + "</tr>"
        for i in range(0, len(cells), COLLAGE_COLUMNS)
    )
    return f"""
            <tr>
              <td style="background:#1c1917;padding:6px 22px 22px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>
              </td>
            </tr>"""


def _card(item: dict) -> str:
    kind = _kind(item)
    title = html_lib.escape(item.get("title") or "Ukendt titel")
    year = item.get("year")
    year_html = (
        f' <span style="color:#a8a29e;font-weight:400;">({html_lib.escape(str(year))})</span>'
        if year is not None
        else ""
    )
    genres = [g for g in (item.get("genres") or []) if isinstance(g, str) and g.strip()][:3]
    rating = rating_text(item.get("rating"))
    overview = shorten(item.get("overview"))
    poster = sized_poster(item.get("poster_url"), "w185")

    meta_parts = [
        f'<span style="display:inline-block;background:{kind["soft"]};color:{kind["ink"]};'
        f"font-size:10px;font-weight:800;letter-spacing:1px;padding:3px 8px;border-radius:999px;\">"
        f'{kind["label"]}</span>'
    ]
    if rating:
        meta_parts.append(
            f'<span style="color:#d97706;font-size:13px;font-weight:700;">&#9733; {rating}</span>'
        )
    if genres:
        meta_parts.append(
            f'<span style="color:#78716c;font-size:12px;">{html_lib.escape(" · ".join(genres))}</span>'
        )
    meta = "&nbsp;&nbsp;".join(meta_parts)

    overview_html = (
        f'<p style="margin:8px 0 0;font-size:13px;line-height:1.5;color:#57534e;">{html_lib.escape(overview)}</p>'
        if overview
        else ""
    )
    if poster:
        thumb = (
            f'<img src="{html_lib.escape(poster)}" alt="" width="76" '
            'style="display:block;width:76px;height:auto;border:0;border-radius:6px;" />'
        )
    else:
        thumb = (
            f'<div style="width:76px;height:114px;border-radius:6px;background:{kind["soft"]};'
            f'color:{kind["ink"]};font-size:26px;line-height:114px;text-align:center;">&#127916;</div>'
        )
    return f"""
                <tr>
                  <td style="padding:0 0 14px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                           style="background:#ffffff;border:1px solid #e7e5e4;border-left:4px solid {kind["color"]};border-radius:10px;">
                      <tr>
                        <td width="92" valign="top" style="padding:12px 0 12px 12px;">{thumb}</td>
                        <td valign="top" style="padding:12px 14px;">
                          <p style="margin:0 0 6px;font-size:16px;font-weight:700;line-height:1.3;color:#1c1917;">{title}{year_html}</p>
                          <p style="margin:0;line-height:1.8;">{meta}</p>{overview_html}
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>"""


def _counter_text(items: list[dict]) -> str:
    tv_count = sum(1 for item in items if item.get("media_kind") == "tv")
    movie_count = len(items) - tv_count
    parts = []
    if movie_count:
        parts.append(f"{movie_count} film")
    if tv_count:
        parts.append(f"{tv_count} {'serie' if tv_count == 1 else 'serier'}")
    return " &middot; ".join(parts)


def render_showcase_email(
    *,
    headline: str,
    tagline: str,
    items: list[dict],
    accent: str = "gold",
    cta_url: str | None = None,
    cta_label: str | None = None,
) -> str:
    """`items` er dicts med `title`, `media_kind` ("movie"/"tv"), og
    valgfrit `year`, `poster_url`, `genres`, `rating`, `overview` — alt
    brugerdata og escapes her (samme begrundelse som
    `render_notification_email`). Collagen vises kun ved mere end én titel;
    ved én titel er kortet nok. Brødteksten (med titel-listen) er bevidst
    IKKE med i HTML-udgaven — kortene viser det samme, rigere; den sendes
    stadig som mailens tekst-alternativ og som beskeden i portalen."""
    accent_color = _ACCENT.get(accent, _ACCENT["gold"])
    safe_headline = html_lib.escape(headline)
    safe_tagline = html_lib.escape(tagline)
    collage = _collage(items) if len(items) > 1 else ""
    cards = "".join(_card(item) for item in items)

    # "1 film" over et enkelt kort siger intet nyt.
    counter = _counter_text(items) if len(items) > 1 else ""
    counter_block = (
        f'<p style="margin:14px 0 0;"><span style="display:inline-block;background:#44403c;'
        f"color:#fde68a;font-size:12px;font-weight:700;letter-spacing:1px;padding:5px 14px;"
        f'border-radius:999px;">{counter}</span></p>'
        if counter
        else ""
    )

    cta_block = ""
    if cta_url and cta_label:
        cta_block = f"""
            <tr>
              <td style="background:#faf7f2;padding:6px 32px 30px;" align="center">
                <a href="{html_lib.escape(cta_url)}"
                   style="display:inline-block;background:{accent_color};color:#fff;font-weight:700;font-size:15px;text-decoration:none;padding:13px 32px;border-radius:999px;">{html_lib.escape(cta_label)}</a>
              </td>
            </tr>"""

    return f"""<!doctype html>
<html lang="da">
  <body style="margin:0;padding:0;background:#f5f1ea;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f1ea;padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:580px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(28,25,23,0.10);">
            <tr>
              <td style="background-color:#1c1917;background-image:linear-gradient(135deg,#1c1917 0%,#451a03 60%,#7c2d12 100%);padding:28px 32px 22px;" align="center">
                <p style="margin:0 0 14px;color:{accent_color};font-size:12px;font-weight:700;letter-spacing:3px;text-transform:uppercase;">&#127916; Voldby BIO &middot; Filmportalen</p>
                <h1 style="margin:0;font-size:26px;line-height:1.25;color:#ffffff;">{safe_headline}</h1>
                <p style="margin:10px 0 0;font-size:15px;line-height:1.5;color:#fcd34d;">{safe_tagline}</p>{counter_block}
              </td>
            </tr>{collage}
            <tr>
              <td style="background:#faf7f2;padding:22px 22px 8px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{cards}
                </table>
              </td>
            </tr>{cta_block}
            <tr>
              <td style="padding:16px 32px;background:#f5f4f2;border-top:1px solid #e7e5e4;" align="center">
                <p style="margin:0;font-size:11px;color:#a8a29e;">Denne mail er sendt fordi du har en e-mail registreret på din konto i Filmportalen. Plakater og data fra TMDb.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
