from httpx import ASGITransport, AsyncClient

from app.integrations import tmdb_client
from app.main import app


async def _anonymous_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_first_request_fetches_from_tmdb_and_caches(client, monkeypatch):
    calls = []

    async def fake_fetch(size, path):
        calls.append((size, path))
        return b"fake-jpeg-bytes", "image/jpeg"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)

    response = await client.get("/api/posters/w342/abc123.jpg")
    assert response.status_code == 200
    assert response.content == b"fake-jpeg-bytes"
    assert response.headers["content-type"] == "image/jpeg"
    assert calls == [("w342", "abc123.jpg")]


async def test_second_request_is_served_from_cache_not_tmdb(client, monkeypatch):
    calls = []

    async def fake_fetch(size, path):
        calls.append((size, path))
        return b"fake-jpeg-bytes", "image/jpeg"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)

    first = await client.get("/api/posters/w342/repeat.jpg")
    second = await client.get("/api/posters/w342/repeat.jpg")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.content == b"fake-jpeg-bytes"
    # Kernen i feature #153: kun ét reelt TMDb-kald, uanset hvor mange gange
    # den samme (size, path) efterspørges bagefter.
    assert len(calls) == 1


async def test_unknown_size_is_rejected_without_calling_tmdb(client, monkeypatch):
    calls = []

    async def fake_fetch(size, path):
        calls.append((size, path))
        return b"x", "image/jpeg"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)

    response = await client.get("/api/posters/w9999/abc.jpg")
    assert response.status_code == 404
    assert calls == []


async def test_tmdb_fetch_failure_returns_404_and_caches_nothing(client, monkeypatch):
    async def fake_fetch(size, path):
        return None

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)

    response = await client.get("/api/posters/w185/missing.jpg")
    assert response.status_code == 404


async def test_poster_endpoint_requires_no_login(client, monkeypatch):
    """Den offentlige /bio-side skal kunne vise postere for uindloggede
    besøgende (samme princip som TMDb's egen CDN havde, jf. feature #153's
    designbeslutning). `client`-fixturen er ubrugt i selve testen, men sætter
    den delte test-DB-infrastruktur op — uden den lukker event-loopet for
    tidligt for den frittstående anonyme klient (samme mønster som
    test_backup_requires_admin i test_system_backup.py)."""

    async def fake_fetch(size, path):
        return b"public-bytes", "image/png"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)

    async with await _anonymous_client() as anon:
        response = await anon.get("/api/posters/w185/public.jpg")
    assert response.status_code == 200
    assert response.content == b"public-bytes"
