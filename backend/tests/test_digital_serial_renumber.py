"""Feature #188 (Jan, 2026-08-21, efter BUGS.md #81's årsag blev forklaret:
"Nulstil til at starte fra 1"). Engangs-omnummerering af D#-serien. Det
testværdige:

- rører ALDRIG fysiske (M#/T#) poster — Jans eksplicitte krav ("vi på ingen
  tidspunkt må røre ved M# serie da de er taget i brug")
- rører aldrig 5000+-puljens numre (helt separat, delt serie)
- omnummererer korrekt i oprettelses-rækkefølge på tværs af BÅDE film og
  TV-serier (D#-serien er delt mellem dem, feature #93)
- tælleren fortsætter korrekt derfra bagefter (næste nye digitale post får
  det rigtige nummer, ikke en kollision med de lige omnummererede)
"""

from datetime import datetime, timezone

from app.repositories import digital_serial_repository

OTHER_SERIAL_START = digital_serial_repository.OTHER_SERIAL_START


async def _insert_movie(db, *, media_type, serial_number, created_at, title="Movie"):
    result = await db["movies"].insert_one(
        {
            "title": title,
            "media_type": media_type,
            "serial_number": serial_number,
            "created_at": created_at,
        }
    )
    return result.inserted_id


async def _insert_tv_show(db, *, media_type, serial_number, created_at, name="Show"):
    result = await db["tv_shows"].insert_one(
        {
            "name": name,
            "media_type": media_type,
            "serial_number": serial_number,
            "created_at": created_at,
        }
    )
    return result.inserted_id


async def test_renumbers_digital_items_from_one_in_creation_order_across_both_collections(db):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 3, tzinfo=timezone.utc)

    # Bevidst IKKE i (movie, show, movie)-rækkefølge efter _id — kun created_at
    # må afgøre den nye nummerering.
    movie_a = await _insert_movie(db, media_type="Digital", serial_number=163, created_at=t1, title="Earliest")
    show_b = await _insert_tv_show(db, media_type="Digital", serial_number=164, created_at=t2, name="Middle")
    movie_c = await _insert_movie(db, media_type="Digital", serial_number=165, created_at=t3, title="Latest")

    renumbered = await digital_serial_repository.renumber_from_one(db)
    assert renumbered == 3

    doc_a = await db["movies"].find_one({"_id": movie_a})
    doc_b = await db["tv_shows"].find_one({"_id": show_b})
    doc_c = await db["movies"].find_one({"_id": movie_c})
    assert doc_a["serial_number"] == 1
    assert doc_b["serial_number"] == 2
    assert doc_c["serial_number"] == 3


async def test_never_touches_physical_movies_or_tv_shows(db):
    """Jan: "vi på ingen tidspunkt må røre ved M# serie da de er taget i
    brug" — samme garanti gælder T#."""
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    digital_movie = await _insert_movie(db, media_type="Digital", serial_number=163, created_at=t1)
    physical_movie = await _insert_movie(
        db, media_type="Fysisk", serial_number=50, created_at=t1, title="Physical Movie"
    )
    physical_show = await _insert_tv_show(
        db, media_type="Fysisk", serial_number=30, created_at=t1, name="Physical Show"
    )

    await digital_serial_repository.renumber_from_one(db)

    assert (await db["movies"].find_one({"_id": digital_movie}))["serial_number"] == 1
    # Uændrede — ikke bare "ikke nulstillet", men bogstaveligt talt urørte.
    assert (await db["movies"].find_one({"_id": physical_movie}))["serial_number"] == 50
    assert (await db["tv_shows"].find_one({"_id": physical_show}))["serial_number"] == 30


async def test_never_touches_the_5000_plus_pool(db):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pool_movie = await _insert_movie(
        db, media_type="Digital", serial_number=OTHER_SERIAL_START + 1, created_at=t1, title="Pool Movie"
    )

    renumbered = await digital_serial_repository.renumber_from_one(db)
    assert renumbered == 0
    assert (await db["movies"].find_one({"_id": pool_movie}))["serial_number"] == OTHER_SERIAL_START + 1


async def test_counter_continues_correctly_after_renumbering(db):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    await _insert_movie(db, media_type="Digital", serial_number=163, created_at=t1)
    await _insert_movie(db, media_type="Digital", serial_number=164, created_at=t2)

    await digital_serial_repository.renumber_from_one(db)

    next_number = await digital_serial_repository.next_serial_number(db)
    assert next_number == 3


async def test_returns_zero_and_does_nothing_when_no_digital_items_exist(db):
    renumbered = await digital_serial_repository.renumber_from_one(db)
    assert renumbered == 0


async def test_endpoint_requires_admin(client):
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin188", "password": "testpassword123"}
        )
        response = await standard_client.post("/api/settings/serial-number/renumber-digital")
        assert response.status_code == 403


async def test_endpoint_renumbers_and_audit_logs(client, db):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await _insert_movie(db, media_type="Digital", serial_number=163, created_at=t1)

    response = await client.post("/api/settings/serial-number/renumber-digital")
    assert response.status_code == 200
    assert response.json() == {"renumbered": 1}

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    matching = [e for e in entries if e["action"] == "digital_serial.renumbered"]
    assert len(matching) == 1
    assert "1 digitale poster" in matching[0]["detail"]
