async def test_default_serial_config(client):
    response = await client.get("/api/settings/serial-number")
    assert response.status_code == 200
    assert response.json() == {"start_number": 1, "increment": 1, "padding_width": 0}


async def test_default_config_produces_sequential_numbers(client):
    first = await client.post("/api/movies", json={"title": "A", "media_type": "Fysisk", "format": "DVD"})
    second = await client.post("/api/movies", json={"title": "B", "media_type": "Fysisk", "format": "DVD"})
    assert first.json()["serial_number"] == 1
    assert second.json()["serial_number"] == 2


async def test_changing_start_number_affects_next_created_movie(client):
    await client.post("/api/movies", json={"title": "A", "media_type": "Fysisk", "format": "DVD"})  # serial_number 1

    response = await client.patch(
        "/api/settings/serial-number", json={"start_number": 100}
    )
    assert response.status_code == 200
    assert response.json()["start_number"] == 100

    second = await client.post("/api/movies", json={"title": "B", "media_type": "Fysisk", "format": "DVD"})
    assert second.json()["serial_number"] == 100


async def test_changing_increment_spaces_out_future_numbers(client):
    """`increment` only changes the step size going forward — it doesn't
    warp whatever the next value already was."""
    await client.post("/api/movies", json={"title": "A", "media_type": "Fysisk", "format": "DVD"})  # serial 1, next_value -> 2
    await client.patch("/api/settings/serial-number", json={"increment": 10})

    second = await client.post("/api/movies", json={"title": "B", "media_type": "Fysisk", "format": "DVD"})  # serial 2, next_value -> 12
    third = await client.post("/api/movies", json={"title": "C", "media_type": "Fysisk", "format": "DVD"})  # serial 12, next_value -> 22

    assert second.json()["serial_number"] == 2
    assert third.json()["serial_number"] == 12


async def test_reconfiguring_start_number_skips_existing_collisions(client):
    """If reconfiguring start/increment would land on an already-assigned
    serial number (e.g. after moving start_number backwards), the generator
    must keep advancing instead of raising a duplicate-key error."""
    for title in ["A", "B", "C"]:
        await client.post("/api/movies", json={"title": title, "media_type": "Fysisk", "format": "DVD"})  # serials 1, 2, 3

    await client.patch("/api/settings/serial-number", json={"start_number": 1})

    fourth = await client.post("/api/movies", json={"title": "D", "media_type": "Fysisk", "format": "DVD"})
    assert fourth.status_code == 201
    assert fourth.json()["serial_number"] not in (1, 2, 3)


async def test_serial_config_rejects_invalid_values(client):
    response = await client.patch("/api/settings/serial-number", json={"increment": 0})
    assert response.status_code == 422

    response = await client.patch(
        "/api/settings/serial-number", json={"padding_width": 11}
    )
    assert response.status_code == 422


async def test_serial_settings_require_authentication(raw_client):
    response = await raw_client.get("/api/settings/serial-number")
    assert response.status_code == 401
