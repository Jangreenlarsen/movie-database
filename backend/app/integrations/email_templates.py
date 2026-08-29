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
) -> str:
    """Alle tekst-argumenter er brugerdata (filmtitler kan være frit
    indtastet ved manuel oprettelse, admins afvisnings-begrundelse er fri
    tekst) og escapes derfor eksplicit — uden det ville en titel/begrundelse
    med `<`/`>` kunne injicere markup i mailen (samme klasse sårbarhed som
    reflekteret XSS, blot i en e-mail-klients HTML-renderer i stedet for en
    browser)."""
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
            </tr>
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
