from httpx import ASGITransport, AsyncClient

from app.integrations import tmdb_client
from app.integrations.tmdb_client import IMAGE_HOST
from app.main import app


async def _anonymous_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_first_request_redirects_to_tmdb_and_caches_in_the_background(client, monkeypatch):
    """BUGS.md #80 (Jan: "nåe man browser film i portal så kommer der lille
    pause være gang der skal hente en ny række film bileder") — et
    cache-miss blokerede tidligere hele forespørgslen på en synkron TMDb-
    hentning. Nu redirectes der med det samme direkte til TMDb's CDN (samme
    hastighed som uden nogen cache overhovedet), mens selve cachningen sker
    i baggrunden."""
    calls = []

    async def fake_fetch(size, path):
        calls.append((size, path))
        return b"fake-jpeg-bytes", "image/jpeg"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)

    response = await client.get("/api/posters/w342/abc123.jpg")
    assert response.status_code == 302
    assert response.headers["location"] == f"{IMAGE_HOST}/w342/abc123.jpg"
    # Baggrunds-cachningen er allerede kørt færdig på dette tidspunkt — en
    # FastAPI `BackgroundTask` afvikles som en del af selve ASGI-svar-
    # sekvensen, som `client.get(...)` afventer fuldt ud.
    assert calls == [("w342", "abc123.jpg")]


async def test_second_request_is_served_from_cache_not_tmdb(client, monkeypatch):
    calls = []

    async def fake_fetch(size, path):
        calls.append((size, path))
        return b"fake-jpeg-bytes", "image/jpeg"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)

    first = await client.get("/api/posters/w342/repeat.jpg")
    second = await client.get("/api/posters/w342/repeat.jpg")
    assert first.status_code == 302
    assert second.status_code == 200
    assert second.content == b"fake-jpeg-bytes"
    assert second.headers["content-type"] == "image/jpeg"
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


async def test_background_cache_failure_does_not_break_the_redirect(client, monkeypatch):
    """En mislykket baggrunds-hentning (TMDb nede/fjernet billede) må ikke
    kaste videre og vælte svaret — brugeren har allerede fået sin redirect;
    fejlen betyder blot at NÆSTE forespørgsel også bliver en redirect."""

    async def fake_fetch(size, path):
        return None

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)

    response = await client.get("/api/posters/w185/missing.jpg")
    assert response.status_code == 302
    assert response.headers["location"] == f"{IMAGE_HOST}/w185/missing.jpg"

    # Stadig ikke cachet — næste forespørgsel er også en redirect, ikke en 500.
    again = await client.get("/api/posters/w185/missing.jpg")
    assert again.status_code == 302


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
    assert response.status_code == 302
    assert response.headers["location"] == f"{IMAGE_HOST}/w185/public.jpg"


async def test_path_traversal_is_rejected_without_calling_tmdb(client, monkeypatch):
    """BUGS.md #108 — "../" i stien slap ud af /t/p/ på image.tmdb.org. Nu
    accepteres kun et TMDb-filnavn; intet hentes, caches eller redirectes."""
    calls = []

    async def fake_fetch(size, path):
        calls.append(path)
        return b"<html></html>", "text/html"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)
    for path in ("..%2F..%2Findex.html", "..%2Fx.jpg", "sub%2Fdir.jpg", "evil.svg", "noext"):
        response = await client.get(f"/api/posters/w342/{path}")
        assert response.status_code == 404, path
    assert calls == []


async def test_non_image_content_is_never_cached(client, monkeypatch):
    """BUGS.md #108 — svarer TMDb med noget andet end et rasterbillede (fx
    SVG eller HTML), gemmes det ikke, og næste kald redirecter blot igen."""
    async def fake_fetch(size, path):
        return b"<svg onload='alert(1)'/>", "image/svg+xml"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)
    first = await client.get("/api/posters/w342/sneaky.jpg")
    second = await client.get("/api/posters/w342/sneaky.jpg")
    assert first.status_code == 302
    assert second.status_code == 302  # stadig ikke cachet


async def test_cached_poster_is_served_with_nosniff(client, monkeypatch):
    async def fake_fetch(size, path):
        return b"jpeg", "image/jpeg; charset=binary"

    monkeypatch.setattr(tmdb_client, "fetch_poster_image", fake_fetch)
    await client.get("/api/posters/w185/ok.jpg")
    cached = await client.get("/api/posters/w185/ok.jpg")
    assert cached.status_code == 200
    assert cached.headers["content-type"] == "image/jpeg"
    assert cached.headers["x-content-type-options"] == "nosniff"
