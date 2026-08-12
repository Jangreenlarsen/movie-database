"""Samlet optaelling til app-hovedet (feature #94)."""

PHYSICAL = {"media_type": "Fysisk", "format": "F-DVD"}
DIGITAL = {"media_type": "Digital", "format": "D-1080"}


async def test_counts_are_zero_for_an_empty_library(client):
    body = (await client.get("/api/library/counts")).json()
    assert body["movies"]["total"] == 0
    assert body["tv_shows"]["total"] == 0


async def test_counts_split_movies_and_tv_shows(client):
    """Film og TV-serier taelles hver for sig — de er to bevidst adskilte
    ressourcer, og et samlet tal ville skjule netop den opdeling."""
    await client.post("/api/movies", json={"title": "Film 1", **PHYSICAL})
    await client.post("/api/movies", json={"title": "Film 2", **DIGITAL})
    await client.post("/api/tv-shows", json={"name": "Serie 1", **PHYSICAL})

    body = (await client.get("/api/library/counts")).json()
    assert body["movies"]["total"] == 2
    assert body["movies"]["physical"] == 1
    assert body["movies"]["digital"] == 1
    assert body["tv_shows"]["total"] == 1
    assert body["tv_shows"]["physical"] == 1


async def test_wishlist_is_counted_separately_not_in_the_total(client):
    """Oenskelisten er ikke noget man "har" — den maa ikke taelle med i
    bibliotekets stoerrelse."""
    await client.post("/api/movies", json={"title": "Ejet", **PHYSICAL})
    await client.post("/api/movies", json={"title": "Oensket", "is_wishlist": True})

    body = (await client.get("/api/library/counts")).json()
    assert body["movies"]["total"] == 1
    assert body["movies"]["wishlist"] == 1


async def test_counts_are_open_to_guests(raw_client):
    """At se hvor meget der staar i biblioteket er ren laesning."""
    await raw_client.post(
        "/api/auth/register", json={"username": "countguest", "password": "testpassword123"}
    )
    response = await raw_client.get("/api/library/counts")
    assert response.status_code == 200


async def test_unclassified_documents_are_reported_separately(db, client):
    """Poster fra foer medietype blev paakraevet (feature #92) taelles med i
    totalen, men hverken som fysiske eller digitale."""
    await db["movies"].insert_one({"title": "Gammel", "is_wishlist": False})

    body = (await client.get("/api/library/counts")).json()
    assert body["movies"]["total"] == 1
    assert body["movies"]["physical"] == 0
    assert body["movies"]["digital"] == 0
    assert body["movies"]["unclassified"] == 1
