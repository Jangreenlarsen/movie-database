"""Serienummer-reglerne fra feature #92 og #93.

Tre serier tælles hver for sig: fysiske film (M#), fysiske TV-serier (T#) og
alle digitale udgaver under ét (D#, delt på tværs af film og serier).
Ønskelisten nummereres ikke. Medietype og format er påkrævet ved oprettelse,
og et skift af medietype flytter posten til den anden serie.
"""

from app.repositories import digital_serial_repository, movie_repository, tv_show_repository

PHYSICAL = {"media_type": "Fysisk", "format": "DVD"}
DIGITAL = {"media_type": "Digital", "format": "D-HD"}


# --- krav om medietype og format --------------------------------------------


async def test_library_movie_requires_media_type_and_format(client):
    response = await client.post("/api/movies", json={"title": "Uklassificeret"})
    assert response.status_code == 422
    assert "media_type" in response.text and "format" in response.text


async def test_library_movie_requires_format_even_with_media_type(client):
    response = await client.post(
        "/api/movies", json={"title": "Halvt Udfyldt", "media_type": "Fysisk"}
    )
    assert response.status_code == 422
    assert "format" in response.text


async def test_library_tv_show_requires_media_type_and_format(client):
    response = await client.post("/api/tv-shows", json={"name": "Uklassificeret"})
    assert response.status_code == 422


async def test_wishlist_is_exempt_from_the_requirement(client):
    """Man ejer ikke det man ønsker sig endnu — der er hverken en fysisk
    udgave at beskrive eller et serienummer at tildele."""
    for path, payload in [
        ("/api/movies", {"title": "Ønsket Film", "is_wishlist": True}),
        ("/api/tv-shows", {"name": "Ønsket Serie", "is_wishlist": True}),
    ]:
        response = await client.post(path, json=payload)
        assert response.status_code == 201, response.text
        assert response.json()["serial_number"] is None


# --- de tre serier ----------------------------------------------------------


async def test_physical_movie_gets_a_number_from_the_movie_series(client):
    response = await client.post("/api/movies", json={"title": "Fysisk Film", **PHYSICAL})
    assert response.status_code == 201
    assert response.json()["serial_number"] == 1


async def test_digital_movie_gets_a_number_from_the_digital_series(client):
    response = await client.post("/api/movies", json={"title": "Digital Film", **DIGITAL})
    assert response.status_code == 201
    assert response.json()["serial_number"] == 1


async def test_digital_movie_does_not_consume_a_physical_number(client):
    """De to serier tælles uafhængigt: en digital post må ikke lave hul i
    M#-rækken, som svarer til rækkefølgen på hylden."""
    await client.post("/api/movies", json={"title": "Fysisk 1", **PHYSICAL})
    await client.post("/api/movies", json={"title": "Digital", **DIGITAL})
    third = await client.post("/api/movies", json={"title": "Fysisk 2", **PHYSICAL})
    assert third.json()["serial_number"] == 2


async def test_physical_and_digital_numbers_may_be_equal(client):
    """M#1 og D#1 er to forskellige udgaver og skal kunne findes side om
    side — det unikke index er derfor sammensat af nummer og medietype."""
    physical = await client.post("/api/movies", json={"title": "Fysisk", **PHYSICAL})
    digital = await client.post("/api/movies", json={"title": "Digital", **DIGITAL})
    assert physical.json()["serial_number"] == 1
    assert digital.json()["serial_number"] == 1


async def test_movies_and_tv_shows_have_separate_physical_series(client):
    """M#-rækken og T#-rækken tælles hver for sig, så M#0001 og T#0001 er to
    forskellige udgaver."""
    movie = await client.post("/api/movies", json={"title": "Første Film", **PHYSICAL})
    show = await client.post("/api/tv-shows", json={"name": "Første Serie", **PHYSICAL})
    assert movie.json()["serial_number"] == 1
    assert show.json()["serial_number"] == 1


async def test_digital_series_is_shared_between_movies_and_tv_shows(client):
    """Jans valg 2026-08-08: én fælles D#-række, så et D#-nummer altid peger
    på præcis én ting — modsat M#/T#, der er adskilte pr. ressource."""
    movie = await client.post("/api/movies", json={"title": "Digital Film", **DIGITAL})
    show = await client.post("/api/tv-shows", json={"name": "Digital Serie", **DIGITAL})
    assert movie.json()["serial_number"] == 1
    assert show.json()["serial_number"] == 2


# --- skift af medietype flytter posten til den anden serie ------------------


async def test_switching_physical_to_digital_moves_it_to_the_digital_series(client):
    """Feature #93 — medietypen bestemmer hvilken serie nummeret hører til,
    så et skift flytter posten frem for bare at fjerne nummeret."""
    await client.post("/api/movies", json={"title": "Digital I Forvejen", **DIGITAL})
    created = await client.post("/api/movies", json={"title": "Solgt DVD", **PHYSICAL})
    movie_id = created.json()["id"]
    assert created.json()["serial_number"] == 1

    response = await client.patch(f"/api/movies/{movie_id}", json={"media_type": "Digital"})
    assert response.status_code == 200
    # Næste ledige i D#-rækken, ikke det gamle M#-nummer.
    assert response.json()["serial_number"] == 2


async def test_switching_digital_to_physical_moves_it_to_the_physical_series(client):
    created = await client.post("/api/movies", json={"title": "Købt På Disk", **DIGITAL})
    movie_id = created.json()["id"]
    assert created.json()["serial_number"] == 1  # D#1

    response = await client.patch(f"/api/movies/{movie_id}", json={"media_type": "Fysisk"})
    assert response.status_code == 200
    assert response.json()["serial_number"] == 1  # M#1 — en anden serie


async def test_switching_tv_show_media_type_follows_the_same_rule(client):
    created = await client.post("/api/tv-shows", json={"name": "Boks-udgave", **PHYSICAL})
    show_id = created.json()["id"]
    assert created.json()["serial_number"] == 1  # T#1

    response = await client.patch(f"/api/tv-shows/{show_id}", json={"media_type": "Digital"})
    assert response.json()["serial_number"] == 1  # D#1


async def test_freed_physical_number_can_be_reused(client):
    """Går en fysisk udgave over til digital, frigives dens M#-nummer og kan
    tildeles igen — ellers ville hullet aldrig blive fyldt."""
    first = await client.post("/api/movies", json={"title": "Nummer 1", **PHYSICAL})
    movie_id = first.json()["id"]
    assert first.json()["serial_number"] == 1

    await client.patch(f"/api/movies/{movie_id}", json={"media_type": "Digital"})
    await client.patch("/api/settings/serial-number", json={"start_number": 1})

    reused = await client.post("/api/movies", json={"title": "Ny Nummer 1", **PHYSICAL})
    assert reused.json()["serial_number"] == 1


async def test_unrelated_update_does_not_touch_the_serial_number(client):
    created = await client.post("/api/movies", json={"title": "Uændret", **PHYSICAL})
    movie_id = created.json()["id"]

    response = await client.patch(f"/api/movies/{movie_id}", json={"personal_note": "God film"})
    assert response.json()["serial_number"] == 1


async def test_moving_to_the_wishlist_clears_the_number_regardless_of_series(client):
    created = await client.post("/api/movies", json={"title": "Fortrudt", **DIGITAL})
    movie_id = created.json()["id"]
    assert created.json()["serial_number"] == 1

    response = await client.patch(f"/api/movies/{movie_id}", json={"is_wishlist": True})
    assert response.json()["serial_number"] is None


# --- engangs-migrering af eksisterende data ---------------------------------


async def test_backfill_assigns_numbers_to_digital_documents_without_one(db):
    """Digitale poster oprettet før de fik deres egen serie — eller ryddet af
    feature #92, hvis dengang-gældende regel var at kun fysiske nummereres —
    skal have et D#-nummer."""
    await db[movie_repository.COLLECTION].insert_one(
        {"title": "Gammel Digital", "media_type": "Digital"}
    )

    assigned = await digital_serial_repository.backfill(db, movie_repository.COLLECTION)

    doc = await db[movie_repository.COLLECTION].find_one({"title": "Gammel Digital"})
    assert assigned == 1
    assert doc["serial_number"] == 1


async def test_backfill_renumbers_digital_document_clashing_with_a_physical_one(db):
    """Poster fra før feature #92: nummeret stammer fra den fysiske serie og
    hører ikke hjemme i D#-rækken."""
    await db[movie_repository.COLLECTION].insert_one(
        {"title": "Fysisk", "media_type": "Fysisk", "serial_number": 4}
    )
    await db[movie_repository.COLLECTION].insert_one(
        {"title": "Digital Med Fysisk Nummer", "media_type": "Digital", "serial_number": 4}
    )

    await digital_serial_repository.backfill(db, movie_repository.COLLECTION)

    digital = await db[movie_repository.COLLECTION].find_one(
        {"title": "Digital Med Fysisk Nummer"}
    )
    physical = await db[movie_repository.COLLECTION].find_one({"title": "Fysisk"})
    assert digital["serial_number"] != 4
    assert physical["serial_number"] == 4


async def test_backfill_is_idempotent(db):
    """Migreringen kører ved hver opstart og må ikke omnummerere noget den
    allerede har rettet."""
    await db[movie_repository.COLLECTION].insert_one(
        {"title": "Gammel Digital", "media_type": "Digital"}
    )

    await digital_serial_repository.backfill(db, movie_repository.COLLECTION)
    first = await db[movie_repository.COLLECTION].find_one({"title": "Gammel Digital"})
    second_run = await digital_serial_repository.backfill(db, movie_repository.COLLECTION)
    after = await db[movie_repository.COLLECTION].find_one({"title": "Gammel Digital"})

    assert second_run == 0
    assert after["serial_number"] == first["serial_number"]


async def test_backfill_leaves_documents_without_media_type_alone(db):
    """En post uden medietype er fra før reglen og kan lige så godt være en
    fysisk udgave hvor feltet aldrig blev udfyldt."""
    await db[movie_repository.COLLECTION].insert_one(
        {"title": "Ukendt Medietype", "serial_number": 9}
    )

    await digital_serial_repository.backfill(db, movie_repository.COLLECTION)

    doc = await db[movie_repository.COLLECTION].find_one({"title": "Ukendt Medietype"})
    assert doc["serial_number"] == 9


async def test_digital_series_skips_a_number_used_in_the_other_collection(db):
    """Den delte D#-serie skal springe et nummer over hvis den anden
    collection allerede bruger det — et index kan ikke håndhæve entydighed
    på tværs af collections."""
    await db[tv_show_repository.COLLECTION].insert_one(
        {"name": "Digital Serie", "media_type": "Digital", "serial_number": 1}
    )

    assigned = await digital_serial_repository.next_serial_number(db)
    assert assigned != 1
