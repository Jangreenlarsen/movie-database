import httpx

from app.integrations import discogs_client


def test_strip_artist_prefix_removes_leading_artist():
    assert discogs_client._strip_artist_prefix("Various - The Matrix") == "The Matrix"


def test_strip_artist_prefix_leaves_title_without_separator_untouched():
    assert discogs_client._strip_artist_prefix("The Matrix") == "The Matrix"


async def test_lookup_title_returns_none_on_empty_results(monkeypatch):
    async def fake_get(self, url, params=None, headers=None):
        return httpx.Response(200, json={"results": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await discogs_client.lookup_title("5051890012345") is None


async def test_lookup_title_cleans_artist_prefix_and_brackets(monkeypatch):
    async def fake_get(self, url, params=None, headers=None):
        return httpx.Response(
            200,
            json={"results": [{"title": "Various - The Matrix (DVD)"}]},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await discogs_client.lookup_title("5051890012345") == "The Matrix"


async def test_lookup_title_never_raises_on_http_error(monkeypatch):
    async def fake_get(self, url, params=None, headers=None):
        raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await discogs_client.lookup_title("5051890012345") is None
