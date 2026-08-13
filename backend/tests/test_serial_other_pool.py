"""Feature #139 — den delte 5000+-pulje for poster hvis ejer ikke er en
jan/lis-variant og som ikke er oprettet af en admin."""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _member(admin_client, name):
    """En aktiv, ikke-admin standard-bruger (må gerne oprette bibliotekspost)."""
    transport = ASGITransport(app=app)
    member = AsyncClient(transport=transport, base_url="http://test")
    register = await member.post(
        "/api/auth/register", json={"username": name, "password": "testpassword123"}
    )
    await admin_client.patch(
        f"/api/users/{register.json()['id']}/status", json={"status": "active"}
    )
    return member


async def test_other_owner_nonadmin_gets_5000_pool(client):
    member = await _member(client, "pool_other")
    resp = await member.post(
        "/api/movies",
        json={"title": "Mormors film", "media_type": "Fysisk", "format": "F-DVD", "owner": "Mormor"},
    )
    assert resp.status_code == 201
    assert resp.json()["serial_number"] == 5000
    await member.aclose()


async def test_standard_owner_nonadmin_uses_normal_series(client):
    member = await _member(client, "pool_std")
    resp = await member.post(
        "/api/movies",
        json={"title": "Vores film", "media_type": "Fysisk", "format": "F-DVD", "owner": "Jan & Lis"},
    )
    assert resp.status_code == 201
    # "Jan & Lis" normaliseres til "jan&lis" → normal M#-serie (starter på 1).
    assert resp.json()["serial_number"] < 5000
    await member.aclose()


async def test_admin_always_uses_normal_series_regardless_of_owner(client):
    # `client` er admin (testuser) — admin-undtagelsen vinder over ejeren.
    resp = await client.post(
        "/api/movies",
        json={"title": "Admin film", "media_type": "Fysisk", "format": "F-DVD", "owner": "Mormor"},
    )
    assert resp.status_code == 201
    assert resp.json()["serial_number"] < 5000


async def test_5000_pool_is_shared_across_movies_and_tv(client):
    member = await _member(client, "pool_shared")
    movie = await member.post(
        "/api/movies",
        json={"title": "Nabo film", "media_type": "Fysisk", "format": "F-DVD", "owner": "Nabo"},
    )
    assert movie.json()["serial_number"] == 5000
    show = await member.post(
        "/api/tv-shows",
        json={"name": "Nabo serie", "media_type": "Digital", "format": "D-1080", "owner": "Nabo"},
    )
    # Én fælles pulje på tværs af film/TV/fysisk/digital → næste er 5001.
    assert show.json()["serial_number"] == 5001
    await member.aclose()


async def test_other_pool_numbers_do_not_pollute_reuse_free_list(client, db):
    """5000+-numre må ikke dukke op som 'huller' i M#-serien (feature #131) —
    ellers ville "Ledige numre" udpege tusindvis af falske ledige tal (3..4999).
    Uden ekskluderingen ville gaps({1,3,5000}) give [2,4,5,…,4999]; med den
    giver gaps({1,3}) = [2]."""
    from app.repositories import movie_repository

    ids = []
    for title in ("M1", "M2", "M3"):
        resp = await client.post(
            "/api/movies", json={"title": title, "media_type": "Fysisk", "format": "F-DVD"}
        )
        ids.append(resp.json()["id"])
    # Slet M#2 → et ægte hul ved 2 i den normale serie.
    await client.delete(f"/api/movies/{ids[1]}")

    # En ikke-admin opretter en "andre ejer"-film → 5000-puljen.
    member = await _member(client, "pool_free")
    other = await member.post(
        "/api/movies",
        json={"title": "Andet", "media_type": "Fysisk", "format": "F-DVD", "owner": "Fremmed"},
    )
    assert other.json()["serial_number"] == 5000
    await member.aclose()

    # Kun det ægte hul (2) — hverken 5000 eller de falske 4..4999.
    free = await movie_repository.free_serial_numbers(db)
    assert free == [2]
