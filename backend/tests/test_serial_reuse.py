"""Feature #131 — genbrug af frigjorte serienumre (til/fra i Indstillinger).

Et "frigjort" nummer = et hul i det brugte interval, opstået når en post
slettes eller flyttes til ønskelisten. Genbrug er slået fra som standard.
"""

PHYSICAL = {"media_type": "Fysisk", "format": "DVD"}
DIGITAL = {"media_type": "Digital", "format": "D-1080"}


async def _create(client, title, extra=None):
    r = await client.post("/api/movies", json={"title": title, **(extra or PHYSICAL)})
    assert r.status_code == 201, r.text
    return r.json()


async def _config(client):
    return (await client.get("/api/settings/serial-number")).json()


async def test_reuse_is_off_by_default_and_leaves_gaps(client):
    a = await _create(client, "A")
    b = await _create(client, "B")
    c = await _create(client, "C")
    assert [a["serial_number"], b["serial_number"], c["serial_number"]] == [1, 2, 3]

    await client.delete(f"/api/movies/{b['id']}")

    # Genbrug er fra: tælleren går videre, hullet (#2) forbliver tomt.
    d = await _create(client, "D")
    assert d["serial_number"] == 4


async def test_config_reports_freed_numbers_and_reuse_flag(client):
    a = await _create(client, "A")
    b = await _create(client, "B")
    await _create(client, "C")
    await client.delete(f"/api/movies/{b['id']}")

    config = await _config(client)
    assert config["reuse_freed"] is False
    assert config["free_numbers"]["physical_movies"] == [2]


async def test_reuse_fills_the_lowest_freed_number(client):
    updated = await client.patch("/api/settings/serial-number", json={"reuse_freed": True})
    assert updated.json()["reuse_freed"] is True

    a = await _create(client, "A")
    b = await _create(client, "B")
    c = await _create(client, "C")
    await client.delete(f"/api/movies/{b['id']}")

    # Genbrug til: den næste post får det laveste frigjorte nummer (#2).
    d = await _create(client, "D")
    assert d["serial_number"] == 2
    # Og hullet er dermed fyldt igen.
    assert (await _config(client))["free_numbers"]["physical_movies"] == []


async def test_reuse_toggle_persists(client):
    await client.patch("/api/settings/serial-number", json={"reuse_freed": True})
    assert (await _config(client))["reuse_freed"] is True
    await client.patch("/api/settings/serial-number", json={"reuse_freed": False})
    assert (await _config(client))["reuse_freed"] is False


async def test_reuse_is_shared_across_the_digital_series(client):
    """D# deles af film og TV-serier — et frigjort D#-hul skal kunne genbruges
    på tværs af begge collections."""
    await client.patch("/api/settings/serial-number", json={"reuse_freed": True})

    m1 = await _create(client, "Dig1", DIGITAL)  # D#1
    m2 = await _create(client, "Dig2", DIGITAL)  # D#2
    tv = await client.post("/api/tv-shows", json={"name": "DigTv", **DIGITAL})  # D#3
    assert [m1["serial_number"], m2["serial_number"], tv.json()["serial_number"]] == [1, 2, 3]

    # Frigør det midterste D#2 (max forbliver 3 pga. TV-serien, så #2 er et hul).
    await client.delete(f"/api/movies/{m2['id']}")
    assert (await _config(client))["free_numbers"]["digital"] == [2]

    reused = await _create(client, "Dig4", DIGITAL)
    assert reused["serial_number"] == 2


async def test_physical_movie_and_tv_series_have_independent_free_numbers(client):
    await client.patch("/api/settings/serial-number", json={"reuse_freed": True})
    ma = await _create(client, "MovA")
    mb = await _create(client, "MovB")
    await _create(client, "MovC")
    await client.post("/api/tv-shows", json={"name": "TvA", **PHYSICAL})
    tvb = await client.post("/api/tv-shows", json={"name": "TvB", **PHYSICAL})
    await client.post("/api/tv-shows", json={"name": "TvC", **PHYSICAL})

    await client.delete(f"/api/movies/{mb['id']}")  # frigør M#2
    await client.delete(f"/api/tv-shows/{tvb.json()['id']}")  # frigør T#2

    config = await _config(client)
    assert config["free_numbers"]["physical_movies"] == [2]
    assert config["free_numbers"]["physical_tv"] == [2]
    assert config["free_numbers"]["digital"] == []
