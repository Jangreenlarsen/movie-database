import logging

import httpx

from app.core.config import settings
from app.core.errors import EmailRateLimitedError

BASE_URL = "https://api.resend.com"

logger = logging.getLogger("moviedb")


async def send_email(to: str, subject: str, text: str) -> bool:
    """Feature #197 — ét HTTP-kald pr. modtager, ALDRIG en samlet `to`-liste
    med flere adresser i samme kald (ville lade modtagere se hinandens
    e-mail via svaret/headerne). Kaster kun `EmailRateLimitedError` (429) —
    kaldere (message_service._send_emails) bruger den til at stoppe resten
    af en udsendelse i stedet for at blive ved med at ramme en allerede
    rate-limitet Resend (CLAUDE.md regel 16). Enhver anden fejl logges og
    giver `False` i stedet for at kaste, så én mislykket e-mail aldrig
    vælter selve besked-oprettelsen i message_service.send()."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{BASE_URL}/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.email_from_address,
                    "to": [to],
                    "subject": subject,
                    "text": text,
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("Resend-afsendelse fejlede (netværksfejl): %s", exc)
        return False

    if response.status_code == 429:
        raise EmailRateLimitedError()
    if response.status_code not in (200, 201):
        logger.warning("Resend afviste afsendelsen (HTTP %s): %s", response.status_code, response.text)
        return False

    logger.info("Resend: e-mail sendt (id=%s)", response.json().get("id"))
    return True


async def test_connection() -> tuple[bool, str]:
    """Feature #75-mønsteret (rigtigt, minimalt testkald mod den aktuelt
    aktive nøgle) — men Resend har en vigtig detalje ingen af de andre
    integrationer har: nøgler kommer i to niveauer, `full_access` og det
    anbefalede, mindst-privilegerede `sending_access` (kan KUN sende, intet
    andet). En `sending_access`-nøgle giver 401 på GET /api-keys selvom den
    er fuldt gyldig til at sende med — samme "samme statuskode, to
    betydninger"-håndtering som upcdatabase_client (BUGS.md #37), her
    afgjort ud fra Resends fejlkode i responsen i stedet for at behandle
    ethvert 401 som en ugyldig nøgle."""
    if not settings.resend_api_key:
        return False, "Ingen Resend-nøgle sat"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{BASE_URL}/api-keys",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            )
    except httpx.HTTPError as exc:
        return False, f"Netværksfejl: {exc}"

    if response.status_code == 200:
        return True, "Virker (fuld adgang)"

    if response.status_code == 401:
        body = response.json() if response.text else {}
        if body.get("name") == "restricted_api_key":
            return True, "Nøglen accepteres (kun sende-adgang)"
        return False, "Resend afviste nøglen (ugyldig)"

    return False, f"Uventet svar (HTTP {response.status_code})"
