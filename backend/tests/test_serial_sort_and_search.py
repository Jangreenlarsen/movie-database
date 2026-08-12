"""Sortering og søgning på serienummer (feature #96).

Tre serier tælles hver for sig (M/T/D), så en sortering på nummeret alene
ville blande dem sammen. Sorteringen grupperer derfor på serie først, og
søgefeltet kan slå et serienummer op med eller uden serie-bogstav.
"""

from app.repositories import movie_repository, tv_show_repository
from app.repositories.text_search import build_text_query

PHYSICAL = {"media_type": "Fysisk", "format": "DVD"}
DIGITAL = {"media_type": "Digital", "format": "D-HD"}


async def _titles(client, **params):
    response = await client.get("/api/movies", params=params)
    assert response.status_code == 200, response.text
    return [m["title"] for m in response.json()["items"]]


# --- sortering --------------------------------------------------------------


async def test_serial_sort_puts_digital_first(client):
    """Jans krav 2026-08-08: alle D-numre først, derefter de fysiske."""
    await client.post("/api/movies", json={"title": "Fysisk A", **PHYSICAL})
    await client.post("/api/movies", json={"title": "Digital A", **DIGITAL})
    await client.post("/api/movies", json={"title": "Fysisk B", **PHYSICAL})
    await client.post("/api/movies", json={"title": "Digital B", **DIGITAL})

    assert await _titles(client, sort="serial_number:asc") == [
        "Digital A",
        "Digital B",
        "Fysisk A",
        "Fysisk B",
    ]


async def test_serial_sort_physical_first_variant(client):
    await client.post("/api/movies", json={"title": "Digital A", **DIGITAL})
    await client.post("/api/movies", json={"title": "Fysisk A", **PHYSICAL})

    assert await _titles(client, sort="serial_number_physical:asc") == ["Fysisk A", "Digital A"]


async def test_direction_flips_numbers_but_not_the_series_grouping(client):
    """Op/ned-knappen må kun vende nummer-rækkefølgen. Vendte den også
    serie-nøglen, ville et klik flytte hele den ene serie hen over den
    anden — hvilket er en anden sortering, ikke den omvendte."""
    await client.post("/api/movies", json={"title": "Digital 1", **DIGITAL})
    await client.post("/api/movies", json={"title": "Digital 2", **DIGITAL})
    await client.post("/api/movies", json={"title": "Fysisk 1", **PHYSICAL})

    assert await _titles(client, sort="serial_number:desc") == [
        "Digital 2",
        "Digital 1",
        "Fysisk 1",
    ]


def test_serial_series_sort_order_depends_on_label_ordering():
    """Sorteringen bygger på at "Digital" står før "Fysisk" alfabetisk.
    Det er en egenskab ved etiketterne, ikke et tilfælde — omdøbes de, skal
    denne test fange det frem for at listen stille skifter rækkefølge."""
    assert "Digital" < "Fysisk"


def test_both_serial_sort_options_expand_to_two_mongo_keys():
    for field in ("serial_number", "serial_number_physical"):
        for repo in (movie_repository, tv_show_repository):
            keys = repo.SORT_FIELDS[field]
            assert [name for name, _ in keys] == ["media_type", "serial_number"]
            # Serie-nøglen er låst, nummeret følger brugerens retning.
            assert keys[0][1] in ("asc", "desc")
            assert keys[1][1] == "user"


# --- søgning ----------------------------------------------------------------


async def test_search_finds_a_movie_by_bare_serial_number(client):
    await client.post("/api/movies", json={"title": "Nummer Et", **PHYSICAL})
    await client.post("/api/movies", json={"title": "Nummer To", **PHYSICAL})

    assert await _titles(client, q="2") == ["Nummer To"]


async def test_search_by_prefixed_serial_narrows_to_that_series(client):
    """M1 og D1 er to forskellige film — søger man med bogstav, skal kun den
    ene komme frem."""
    await client.post("/api/movies", json={"title": "Fysisk Et", **PHYSICAL})
    await client.post("/api/movies", json={"title": "Digital Et", **DIGITAL})

    assert await _titles(client, q="M1") == ["Fysisk Et"]
    assert await _titles(client, q="D1") == ["Digital Et"]


async def test_bare_number_finds_both_series(client):
    await client.post("/api/movies", json={"title": "Fysisk Et", **PHYSICAL})
    await client.post("/api/movies", json={"title": "Digital Et", **DIGITAL})

    assert sorted(await _titles(client, q="1")) == ["Digital Et", "Fysisk Et"]


async def test_search_accepts_padded_and_lowercase_serial(client):
    """Nummeret vises med foranstillede nuller, så man skal kunne søge på det
    som det står — og uden at tænke over versalen."""
    await client.post("/api/movies", json={"title": "Fysisk Et", **PHYSICAL})

    assert await _titles(client, q="m0001") == ["Fysisk Et"]
    assert await _titles(client, q="M0001") == ["Fysisk Et"]


async def test_serial_search_works_for_tv_shows_with_t_prefix(client):
    await client.post("/api/tv-shows", json={"name": "Fysisk Serie", **PHYSICAL})
    response = await client.get("/api/tv-shows", params={"q": "T1"})
    assert [s["name"] for s in response.json()["items"]] == ["Fysisk Serie"]


async def test_unknown_prefix_falls_back_to_text_search(client):
    """"S1" er ikke et serie-bogstav vi kender, så ordet skal behandles som
    almindelig tekst i stedet for at matche ingenting."""
    await client.post("/api/movies", json={"title": "Sæson S1 Special", **PHYSICAL})

    assert await _titles(client, q="S1") == ["Sæson S1 Special"]


async def test_serial_search_combines_with_other_terms(client):
    """Alle ord skal matche, men hvert ord må matche hvert sit felt — så
    "matrix 1" finder filmen hvis titlen matcher det ene og nummeret det
    andet."""
    await client.post("/api/movies", json={"title": "The Matrix", **PHYSICAL})
    await client.post("/api/movies", json={"title": "The Matrix Reloaded", **PHYSICAL})

    assert await _titles(client, q="matrix 1") == ["The Matrix"]


def test_build_text_query_without_prefixes_ignores_serial_terms():
    """Uden serie-præfikser slås serienummer-søgningen fra — kaldere der
    ikke har en nummer-serie får den gamle, rene tekstsøgning."""
    query = build_text_query("42", ["title"])
    # Kun tekst-alternativet, ingen nummer-gren.
    assert list(query["$or"][0]) == ["title"]
    assert len(query["$or"]) == 1

    with_prefixes = build_text_query("42", ["title"], {"M": "Fysisk"})
    assert {"serial_number": 42} in with_prefixes["$or"]


# --- print-listens kolonner (feature #98) ------------------------------------


async def test_every_print_list_column_is_a_valid_sort_field(client):
    """Print-listens kolonne-overskrifter sorterer via API'ets `sort`-parameter.
    Ukendte felter droppes stiltiende af `parse_sort_param`, så en tastefejl
    ville vise sig som "sorteringen gør ingenting" frem for som en fejl —
    derfor tjekkes hvert felt her mod den faktiske whitelist."""
    movie_fields = ["serial_number", "title", "year", "format", "audio_types", "location"]
    tv_fields = ["serial_number", "name", "year", "format", "audio_types", "location"]

    for field in movie_fields:
        assert field in movie_repository.SORT_FIELDS, field
    for field in tv_fields:
        assert field in tv_show_repository.SORT_FIELDS, field


async def test_sorting_by_audio_type_works_end_to_end(client):
    """Den nye kolonne i print-listen. Mongo sorterer et array efter dets
    mindste element, hvilket er den orden en liste over lydformater læses i."""
    await client.post(
        "/api/movies",
        json={"title": "Med DTS", "audio_types": ["DTS"], **PHYSICAL},
    )
    await client.post(
        "/api/movies",
        json={"title": "Med Atmos", "audio_types": ["Atmos"], **PHYSICAL},
    )

    assert await _titles(client, sort="audio_types:asc") == ["Med Atmos", "Med DTS"]


async def test_sorting_by_order_status_works_end_to_end(client):
    """Feature #127 — bestillingsstatus er sorterbar (kun sat på ønskeliste-
    poster, feature #114). Var feltet ikke whitelistet, ville `parse_sort_param`
    droppe det stiltiende og faldet tilbage til standard-sorteringen — så en
    forkert rækkefølge her fanger netop det."""
    await client.post(
        "/api/movies",
        json={"title": "iMusic-film", "is_wishlist": True, "order_status": "Bestilt ved iMusic"},
    )
    await client.post(
        "/api/movies",
        json={"title": "Div-film", "is_wishlist": True, "order_status": "Bestilt ved div."},
    )

    # "Bestilt ved div." < "Bestilt ved iMusic" (d < i) — samme rækkefølge i
    # både mongomock og MongoDB (ren streng-sammenligning).
    assert await _titles(client, wishlist="true", sort="order_status:asc") == [
        "Div-film",
        "iMusic-film",
    ]
    assert await _titles(client, wishlist="true", sort="order_status:desc") == [
        "iMusic-film",
        "Div-film",
    ]
