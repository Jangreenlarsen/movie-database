"""BUGS.md #105 — sikker JSON-afkodning af svar fra eksterne tjenester.

`response.json()` kaster `ValueError` (JSONDecodeError), hvis en tjeneste
svarer 200 med noget der ikke er JSON — fx en Cloudflare-udfordring, en
captive portal eller en proxy-fejlside. Uden dette slap den rå fejl igennem
som en 500 midt i scanningsflowet, selv i klienter der lover aldrig at
kaste. Kaldestedet afgør selv hvad "ugyldigt svar" betyder for det (intet
match, en pæn fejl, "Test forbindelse" fejler)."""

from typing import Any

import httpx


def parse_json(response: httpx.Response) -> Any | None:
    """Det afkodede JSON, eller None hvis svaret ikke er gyldig JSON."""
    try:
        return response.json()
    except ValueError:
        return None


def json_object(response: httpx.Response) -> dict | None:
    """Som `parse_json`, men kun et JSON-objekt tæller — de fleste tjenester
    svarer med et objekt, og `.get(...)` på en liste ville ellers kaste en
    ny, lige så rå fejl."""
    data = parse_json(response)
    return data if isinstance(data, dict) else None
