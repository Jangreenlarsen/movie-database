import httpx

from app.core.config import settings
from app.integrations import upcdatabase_client


async def test_lookup_title_returns_none_when_no_token_configured(monkeypatch):
    """Unlike Discogs (token merely raises a rate-limit), UPCDatabase.org
    requires auth — an empty token must short-circuit before ever making a
    network call, not attempt an unauthenticated request that will 403."""

    async def fake_get(self, url, headers=None):
        raise AssertionError("should not be called when no token is configured")

    monkeypatch.setattr(settings, "upcdatabase_token", "")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await upcdatabase_client.lookup_title("5051890012345") is None


async def test_lookup_title_returns_title_on_success(monkeypatch):
    async def fake_get(self, url, headers=None):
        assert url == "https://api.upcdatabase.org/product/5051890012345"
        assert headers == {"Authorization": "Bearer test-token"}
        return httpx.Response(
            200,
            json={"success": True, "title": "The Matrix (DVD)"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(settings, "upcdatabase_token", "test-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await upcdatabase_client.lookup_title("5051890012345") == "The Matrix"


async def test_lookup_title_returns_none_when_not_found(monkeypatch):
    async def fake_get(self, url, headers=None):
        return httpx.Response(404, json={"success": False}, request=httpx.Request("GET", url))

    monkeypatch.setattr(settings, "upcdatabase_token", "test-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await upcdatabase_client.lookup_title("0000000000000") is None


async def test_lookup_title_returns_none_on_invalid_key(monkeypatch):
    async def fake_get(self, url, headers=None):
        return httpx.Response(403, json={"success": False}, request=httpx.Request("GET", url))

    monkeypatch.setattr(settings, "upcdatabase_token", "bad-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await upcdatabase_client.lookup_title("5051890012345") is None


async def test_lookup_title_never_raises_on_http_error(monkeypatch):
    async def fake_get(self, url, headers=None):
        raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(settings, "upcdatabase_token", "test-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await upcdatabase_client.lookup_title("5051890012345") is None
