"""Serienummer-reglerne fra feature #92.

Kun fysiske biblioteksposter nummereres, medietype+format er påkrævet ved
oprettelse, og reglen håndhæves begge veje når medietypen ændres senere.
Film og TV-serier har hver sin nummer-serie.
"""

from app.repositories import movie_repository, tv_show_repository

PHYSICAL = {"media_type": "Fysisk", "format": "DVD"}
DIGITAL = {"media_type": "Digital", "format": "Digital-HD"}


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


# --- kun fysiske får nummer -------------------------------------------------


async def test_physical_movie_gets_a_serial_number(client):
    response = await client.post("/api/movies", json={"title": "Fysisk Film", **PHYSICAL})
    assert response.status_code == 201
    assert response.json()["serial_number"] == 1


async def test_digital_movie_gets_no_serial_number(client):
    response = await client.post("/api/movies", json={"title": "Digital Film", **DIGITAL})
    assert response.status_code == 201
    assert response.json()["serial_number"] is None


async def test_digital_movie_does_not_consume_a_number(client):
    """Nummer-serien må ikke få huller af digitale poster — den svarer til
    rækkefølgen på hylden."""
    await client.post("/api/movies", json={"title": "Fysisk 1", **PHYSICAL})
    await client.post("/api/movies", json={"title": "Digital", **DIGITAL})
    third = await client.post("/api/movies", json={"title": "Fysisk 2", **PHYSICAL})
    assert third.json()["serial_number"] == 2


async def test_digital_tv_show_gets_no_serial_number(client):
    response = await client.post("/api/tv-shows", json={"name": "Digital Serie", **DIGITAL})
    assert response.status_code == 201
    assert response.json()["serial_number"] is None


async def test_movies_and_tv_shows_have_separate_number_series(client):
    """Jans krav 2026-08-08: M#-serien og T#-serien tælles hver for sig, så
    M#0001 og T#0001 er to forskellige udgaver."""
    movie = await client.post("/api/movies", json={"title": "Første Film", **PHYSICAL})
    show = await client.post("/api/tv-shows", json={"name": "Første Serie", **PHYSICAL})
    assert movie.json()["serial_number"] == 1
    assert show.json()["serial_number"] == 1


# --- reglen håndhæves begge veje ved ændring --------------------------------


async def test_switching_physical_to_digital_clears_the_serial_number(client):
    created = await client.post("/api/movies", json={"title": "Solgt DVD", **PHYSICAL})
    movie_id = created.json()["id"]
    assert created.json()["serial_number"] == 1

    response = await client.patch(f"/api/movies/{movie_id}", json={"media_type": "Digital"})
    assert response.status_code == 200
    assert response.json()["serial_number"] is None


async def test_switching_digital_to_physical_assigns_a_serial_number(client):
    created = await client.post("/api/movies", json={"title": "Købt På Disk", **DIGITAL})
    movie_id = created.json()["id"]
    assert created.json()["serial_number"] is None

    response = await client.patch(f"/api/movies/{movie_id}", json={"media_type": "Fysisk"})
    assert response.status_code == 200
    assert response.json()["serial_number"] == 1


async def test_freed_number_can_be_reused(client):
    """Går en fysisk udgave over til digital, skal dens nummer kunne
    genbruges — ellers ville hullet aldrig blive fyldt."""
    first = await client.post("/api/movies", json={"title": "Nummer 1", **PHYSICAL})
    movie_id = first.json()["id"]
    assert first.json()["serial_number"] == 1

    await client.patch(f"/api/movies/{movie_id}", json={"media_type": "Digital"})
    await client.patch("/api/settings/serial-number", json={"start_number": 1})

    reused = await client.post("/api/movies", json={"title": "Ny Nummer 1", **PHYSICAL})
    assert reused.json()["serial_number"] == 1


async def test_switching_tv_show_media_type_follows_the_same_rule(client):
    created = await client.post("/api/tv-shows", json={"name": "Boks-udgave", **PHYSICAL})
    show_id = created.json()["id"]
    assert created.json()["serial_number"] == 1

    response = await client.patch(f"/api/tv-shows/{show_id}", json={"media_type": "Digital"})
    assert response.json()["serial_number"] is None


async def test_unrelated_update_does_not_touch_the_serial_number(client):
    created = await client.post("/api/movies", json={"title": "Uændret", **PHYSICAL})
    movie_id = created.json()["id"]

    response = await client.patch(f"/api/movies/{movie_id}", json={"personal_note": "God film"})
    assert response.json()["serial_number"] == 1


# --- engangs-oprydning af eksisterende data ---------------------------------


async def test_migration_strips_serial_numbers_from_digital_documents(db):
    """Feature #92's oprydning: digitale poster oprettet før reglen fandtes,
    må ikke blive ved med at optage numre i den fysiske serie."""
    await db[movie_repository.COLLECTION].insert_one(
        {"title": "Gammel Digital", "media_type": "Digital", "serial_number": 7}
    )
    await db[movie_repository.COLLECTION].insert_one(
        {"title": "Gammel Fysisk", "media_type": "Fysisk", "serial_number": 8}
    )

    await movie_repository._migrate_digital_serial_numbers(db)

    digital = await db[movie_repository.COLLECTION].find_one({"title": "Gammel Digital"})
    physical = await db[movie_repository.COLLECTION].find_one({"title": "Gammel Fysisk"})
    # Nøglen fjernes helt, ikke sat til null — så det sparse unikke index
    # aldrig ser to poster kollidere på ingenting.
    assert "serial_number" not in digital
    assert physical["serial_number"] == 8


async def test_migration_leaves_documents_without_media_type_alone(db):
    """En post uden medietype er fra før reglen og kan lige så godt være en
    fysisk udgave hvor feltet aldrig blev udfyldt. At fjerne dens nummer
    ville slette noget der kan stå skrevet på et cover."""
    await db[movie_repository.COLLECTION].insert_one(
        {"title": "Ukendt Medietype", "serial_number": 9}
    )

    await movie_repository._migrate_digital_serial_numbers(db)

    doc = await db[movie_repository.COLLECTION].find_one({"title": "Ukendt Medietype"})
    assert doc["serial_number"] == 9


async def test_migration_covers_tv_shows_too(db):
    await db[tv_show_repository.COLLECTION].insert_one(
        {"name": "Gammel Digital Serie", "media_type": "Digital", "serial_number": 3}
    )

    await tv_show_repository._migrate_digital_serial_numbers(db)

    doc = await db[tv_show_repository.COLLECTION].find_one({"name": "Gammel Digital Serie"})
    assert "serial_number" not in doc
