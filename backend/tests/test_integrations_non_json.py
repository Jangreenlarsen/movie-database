"""BUGS.md #105 — eksterne tjenester der svarer 200 med noget der ikke er
JSON (Cloudflare-udfordring, captive portal, proxy-fejlside), må aldrig
give en rå 500. Hver klient skal oversætte det til sit eget "intet
match"/pæn fejl/"Test forbindelse fejlede"."""

import httpx
import pytest

from app.core.config import settings
from app.core.errors import TmdbUnavailableError
from app.integrations import (
    discogs_client,
    ean_search_client,
    email_client,
    omdb_client,
    tmdb_client,
    upc_client,
    upcdatabase_client,
)

HTML = "<html><body>Just a moment...</body></html>"


@pytest.fixture
def html_everywhere(monkeypatch):
    async def fake(self, url, **kwargs):
        return httpx.Response(200, text=HTML, request=httpx.Request("GET", str(url)))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake)
    for key in (
        "tmdb_api_token",
        "discogs_token",
        "ean_search_api_key",
        "upcdatabase_token",
        "omdb_api_key",
        "resend_api_key",
    ):
        monkeypatch.setattr(settings, key, "x", raising=False)


async def test_barcode_lookups_treat_non_json_as_no_match(html_everywhere):
    assert await upc_client.lookup_title("5051892004422") is None
    assert await discogs_client.lookup_title("5051892004422") is None
    assert await ean_search_client.lookup_title("5051892004422") is None
    assert await upcdatabase_client.lookup_title("5051892004422") is None


async def test_omdb_rating_falls_back_on_non_json(html_everywhere):
    assert await omdb_client.get_imdb_rating("tt0078748") is None


@pytest.mark.parametrize("call", [
    lambda: tmdb_client.search_movies("Alien"),
    lambda: tmdb_client.search_tv("Alien"),
    lambda: tmdb_client.get_movie_details(348),
    lambda: tmdb_client.get_tv_show_details(1396),
])
async def test_tmdb_non_json_is_a_clean_unavailable_error(html_everywhere, call):
    with pytest.raises(TmdbUnavailableError):
        await call()


async def test_connection_tests_do_not_report_success_on_html(html_everywhere):
    # Før: EAN-Search og UPCDatabase svarede "Virker" / kastede på en HTML-side.
    for client in (ean_search_client, upcdatabase_client, omdb_client):
        ok, message = await client.test_connection()
        assert ok is False, f"{client.__name__}: {message}"


async def test_sent_email_stays_sent_even_if_reply_is_not_json(html_everywhere):
    assert await email_client.send_email("a@example.com", "Emne", "Tekst") is True
