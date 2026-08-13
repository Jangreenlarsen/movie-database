"""Feature #145 — badge på et ønske hvis navnet falder sammen med en titel der
allerede er i biblioteket (film ELLER TV)."""


async def _wishlist(client):
    return (await client.get("/api/movies", params={"wishlist": "true"})).json()["items"]


async def _tv_wishlist(client):
    return (await client.get("/api/tv-shows", params={"wishlist": "true"})).json()["items"]


async def test_flag_set_when_title_matches_a_library_movie(client):
    await client.post(
        "/api/movies", json={"title": "Dune", "media_type": "Fysisk", "format": "F-DVD"}
    )
    await client.post("/api/movies", json={"title": "Dune", "is_wishlist": True})
    await client.post("/api/movies", json={"title": "Ukendt Film", "is_wishlist": True})

    by_title = {m["title"]: m for m in await _wishlist(client)}
    assert by_title["Dune"]["name_in_library"] is True
    assert by_title["Ukendt Film"]["name_in_library"] is False


async def test_match_is_case_and_whitespace_insensitive(client):
    await client.post(
        "/api/movies", json={"title": "The Matrix", "media_type": "Fysisk", "format": "F-DVD"}
    )
    await client.post("/api/movies", json={"title": "  the matrix  ", "is_wishlist": True})
    items = await _wishlist(client)
    assert items[0]["name_in_library"] is True


async def test_cross_type_wishlist_movie_matches_library_tv(client):
    # Navne-sammenfald på tværs af film/TV skal også fanges (Jan: "film eller tv").
    await client.post(
        "/api/tv-shows", json={"name": "Fargo", "media_type": "Fysisk", "format": "F-DVD"}
    )
    await client.post("/api/movies", json={"title": "Fargo", "is_wishlist": True})
    items = await _wishlist(client)
    assert items[0]["name_in_library"] is True


async def test_cross_type_wishlist_tv_matches_library_movie(client):
    await client.post(
        "/api/movies", json={"title": "It", "media_type": "Fysisk", "format": "F-DVD"}
    )
    await client.post("/api/tv-shows", json={"name": "It", "is_wishlist": True})
    items = await _tv_wishlist(client)
    assert items[0]["name_in_library"] is True
