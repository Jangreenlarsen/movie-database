import httpx

from app.core.config import settings
from app.integrations import ean_search_client


async def test_lookup_title_returns_none_when_no_token_configured(monkeypatch):
    async def fake_get(self, url, params=None):
        raise AssertionError("should not be called when no token is configured")

    monkeypatch.setattr(settings, "ean_search_api_key", "")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await ean_search_client.lookup_title("5051890012345") is None


async def test_lookup_title_returns_title_on_success(monkeypatch):
    async def fake_get(self, url, params=None):
        assert url == ean_search_client.BASE_URL
        assert params == {
            "token": "test-token",
            "op": "barcode-lookup",
            "format": "json",
            "ean": "5051890012345",
        }
        return httpx.Response(
            200,
            json=[{"ean": "5051890012345", "name": "The Matrix (DVD)"}],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(settings, "ean_search_api_key", "test-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await ean_search_client.lookup_title("5051890012345") == "The Matrix"


async def test_lookup_title_returns_none_when_no_match(monkeypatch):
    async def fake_get(self, url, params=None):
        return httpx.Response(200, json=[], request=httpx.Request("GET", url))

    monkeypatch.setattr(settings, "ean_search_api_key", "test-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await ean_search_client.lookup_title("0000000000000") is None


async def test_lookup_title_returns_none_and_warns_on_rejected_token(monkeypatch):
    async def fake_get(self, url, params=None):
        return httpx.Response(
            200, json=[{"error": "Invalid token"}], request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(settings, "ean_search_api_key", "bad-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await ean_search_client.lookup_title("5051890012345") is None


async def test_lookup_title_never_raises_on_http_error(monkeypatch):
    async def fake_get(self, url, params=None):
        raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(settings, "ean_search_api_key", "test-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await ean_search_client.lookup_title("5051890012345") is None


async def test_test_connection_reports_ok_on_success(monkeypatch):
    async def fake_get(self, url, params=None):
        return httpx.Response(
            200, json=[{"ean": "5099750442227", "name": "Thriller"}], request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(settings, "ean_search_api_key", "test-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    ok, message = await ean_search_client.test_connection()
    assert ok is True


async def test_test_connection_reports_failure_on_rejected_token(monkeypatch):
    async def fake_get(self, url, params=None):
        return httpx.Response(
            200, json=[{"error": "Invalid token"}], request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(settings, "ean_search_api_key", "bad-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    ok, message = await ean_search_client.test_connection()
    assert ok is False
    assert "Invalid token" in message


async def test_test_connection_reports_failure_when_no_token_set(monkeypatch):
    monkeypatch.setattr(settings, "ean_search_api_key", "")
    ok, message = await ean_search_client.test_connection()
    assert ok is False
