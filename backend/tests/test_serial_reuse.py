"""Feature #131 — genbrug af frigjorte serienumre (til/fra i Indstillinger).

Et "frigjort" nummer = et hul i det brugte interval, opstået når en post
slettes eller flyttes til ønskelisten. Genbrug er slået fra som standard.
"""

PHYSICAL = {"media_type": "Fysisk", "format": "F-DVD"}
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


async def test_create_retries_on_serial_collision(client, monkeypatch):
    """BUGS.md #62 — genbrug af frigjorte numre er ikke atomisk, så to samtidige
    oprettelser kan gribe samme nummer. En serienr-kollision skal retry'es (med
    et frisk nummer), ikke fejlagtigt meldes som stregkode-dublet."""
    from pymongo.errors import DuplicateKeyError

    from app.repositories import movie_repository

    original_insert = movie_repository.insert
    calls = {"n": 0}

    async def flaky_insert(db, document):
        calls["n"] += 1
        if calls["n"] == 1:
            # Simuler at en samtidig oprettelse nåede samme serienummer først.
            raise DuplicateKeyError(
                "E11000 duplicate key error index: serial_number_media_type "
                "dup key: { serial_number: 1 }"
            )
        return await original_insert(db, document)

    monkeypatch.setattr(movie_repository, "insert", flaky_insert)

    response = await client.post("/api/movies", json={"title": "Retry", **PHYSICAL})
    assert response.status_code == 201, response.text
    assert calls["n"] == 2  # første insert fejlede på serienr, anden lykkedes


async def test_barcode_collision_still_raises_duplicate_barcode(client):
    """BUGS.md #62 — retry-løkken må kun retry'e serienr-kollisioner; en ægte
    stregkode-dublet skal fortsat give 409 DuplicateBarcode (ikke retry i det
    uendelige eller forkert fejltype)."""
    await client.post("/api/movies", json={"title": "First", "barcode": "5711111111111", **PHYSICAL})
    dup = await client.post("/api/movies", json={"title": "Second", "barcode": "5711111111111", **PHYSICAL})
    assert dup.status_code == 409


async def test_freed_trailing_numbers_are_recognized_immediately(client):
    """BUGS.md #83 (Jan: "vi har i M# serie 1,2,3,4,5,6 ... sletter vi nr 5,6
    og de bliver fri men tæller bliver på 7 så når vi registrere en ny film
    få den nr 7"). Sletter man de ØVERSTE numre i serien (ikke et hul midt i),
    skal de vises som ledige med det samme — ikke først efter at en senere
    post tilfældigvis får et endnu højere nummer og dermed trækker dem "ind i"
    det brugte interval igen."""
    a = await _create(client, "A")
    b = await _create(client, "B")
    c = await _create(client, "C")
    d = await _create(client, "D")
    e = await _create(client, "E")
    f = await _create(client, "F")
    assert [x["serial_number"] for x in (a, b, c, d, e, f)] == [1, 2, 3, 4, 5, 6]

    await client.delete(f"/api/movies/{e['id']}")
    await client.delete(f"/api/movies/{f['id']}")

    # Ledige-numre-oversigten skal vise #5,#6 med det samme — FØR noget som
    # helst andet får et nyt, højere nummer.
    assert (await _config(client))["free_numbers"]["physical_movies"] == [5, 6]

    await client.patch("/api/settings/serial-number", json={"reuse_freed": True})
    g = await _create(client, "G")
    assert g["serial_number"] == 5


async def test_free_numbers_list_is_capped_even_with_a_huge_gap(client):
    """BUGS.md #86 (Jan: "hvis en adm opretter en film med et nr på 50000,
    så vil den genbrugs list indholde alle nr fra den sidste ca omkring 500
    til 49999, det giver ikke mening") — et loft på 100 (Jans valg: "jeg
    tænker max på 100") forhindrer at ét usædvanligt højt nummer får listen
    til at indeholde titusindvis af "ledige" numre. Bruger 4999 (lige under
    `OTHER_SERIAL_START`s 5000-grænse for den helt separate delte pulje,
    feature #139) frem for Jans eget 50000-eksempel, som reelt ville lande i
    DEN pulje og slet ikke tælle med i M#-seriens egen gaps-beregning."""
    a = await _create(client, "A")
    b = await _create(client, "B")
    resp = await client.patch(f"/api/movies/{b['id']}", json={"serial_number": 4999})
    assert resp.status_code == 200, resp.text

    free = (await _config(client))["free_numbers"]["physical_movies"]
    assert len(free) == 100
    # De laveste numre først (dem der rent faktisk genbruges/vises), ikke et
    # tilfældigt udsnit af det enorme interval.
    assert free[0] == 2
    assert free[-1] == 101


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
