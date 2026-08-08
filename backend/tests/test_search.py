"""Fritekst-søgning (`?q=`) — BUGS.md #48.

Søgningen var helt utestet før denne fil, fordi den gik gennem Mongos
`$text`, som mongomock ikke implementerer. Efter #48 er den et almindeligt
regex-match og dermed testbar i den suite der findes.
"""

from app.repositories import tv_show_repository
from app.repositories.text_search import build_text_query


async def _movie(client, **fields):
    payload = {"title": "Untitled", **fields}
    created = await client.post("/api/movies", json=payload)
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def _titles(client, query):
    response = await client.get("/api/movies", params={"q": query})
    assert response.status_code == 200
    return {m["title"] for m in response.json()["items"]}


async def test_search_matches_cast_member(client):
    """Kernen i #48: et skuespillernavn i søgefeltet fandt før ingenting."""
    await _movie(client, title="Heat", cast=["Al Pacino", "Robert De Niro"])
    await _movie(client, title="Amélie", cast=["Audrey Tautou"])

    assert await _titles(client, "Pacino") == {"Heat"}


async def test_search_matches_director(client):
    await _movie(client, title="Heat", director="Michael Mann")
    await _movie(client, title="Amélie", director="Jean-Pierre Jeunet")

    assert await _titles(client, "Michael Mann") == {"Heat"}


async def test_search_matches_genre(client):
    await _movie(client, title="Heat", genres=["Crime", "Thriller"])
    await _movie(client, title="Amélie", genres=["Comedy", "Romance"])

    assert await _titles(client, "Romance") == {"Amélie"}


async def test_search_still_matches_title_and_overview(client):
    await _movie(client, title="Heat", overview="A crew of professional thieves.")
    await _movie(client, title="Amélie", overview="A shy waitress in Paris.")

    assert await _titles(client, "Heat") == {"Heat"}
    assert await _titles(client, "waitress") == {"Amélie"}


async def test_search_is_case_insensitive(client):
    await _movie(client, title="Heat", cast=["Al Pacino"])

    assert await _titles(client, "pAcInO") == {"Heat"}


async def test_search_matches_partial_word(client):
    """`$text` matchede kun hele ord, så et søgefelt der søger pr. tastetryk
    gav nul resultater indtil ordet var skrevet færdigt."""
    await _movie(client, title="Heat", cast=["Al Pacino"])

    assert await _titles(client, "Paci") == {"Heat"}


async def test_all_terms_must_match_but_may_span_fields(client):
    await _movie(client, title="Heat", cast=["Al Pacino"])
    await _movie(client, title="Scarface", cast=["Al Pacino"])
    await _movie(client, title="Heat Wave", cast=["Someone Else"])

    # Begge ord skal findes, men gerne i hver sit felt.
    assert await _titles(client, "pacino heat") == {"Heat"}


async def test_search_with_no_match_returns_empty(client):
    await _movie(client, title="Heat", cast=["Al Pacino"])

    assert await _titles(client, "De Niro") == set()


async def test_regex_metacharacters_are_treated_as_text(client):
    """En søgning på fx "(2019)" må hverken brække eller opføre sig som et
    regulært udtryk."""
    await _movie(client, title="Movie (2019)")
    await _movie(client, title="Movie 2019")

    assert await _titles(client, "(2019)") == {"Movie (2019)"}


async def test_search_combines_with_tag_filter(client):
    await _movie(client, title="Heat", cast=["Al Pacino"], tags=["Krimi"])
    await _movie(client, title="Scarface", cast=["Al Pacino"], tags=["Klassiker"])

    response = await client.get("/api/movies", params={"q": "Pacino", "tags": "Krimi"})
    assert {m["title"] for m in response.json()["items"]} == {"Heat"}


async def test_search_matches_tv_show_cast(client):
    await client.post("/api/tv-shows", json={"name": "The Americans", "cast": ["Keri Russell"]})
    await client.post("/api/tv-shows", json={"name": "Fleabag", "cast": ["Phoebe Waller-Bridge"]})

    by_cast = await client.get("/api/tv-shows", params={"q": "Keri"})
    assert {s["name"] for s in by_cast.json()["items"]} == {"The Americans"}


def test_tv_search_covers_creators():
    """`creators` kan kun komme fra TMDb (`TvShowCreate` har ikke feltet), så
    den vej kan ikke rammes end-to-end i denne suite — men feltet skal være
    med i søgningen, hvilket er det der kan tjekkes her."""
    assert "creators" in tv_show_repository.TEXT_SEARCH_FIELDS

    query = build_text_query("weisberg", tv_show_repository.TEXT_SEARCH_FIELDS)
    assert any("creators" in clause for clause in query["$or"])


async def test_blank_query_returns_everything(client):
    """En tom/whitespace-only søgning må ikke filtrere noget fra."""
    await _movie(client, title="Heat")
    await _movie(client, title="Amélie")

    assert build_text_query("   ", ["title"]) is None
    assert await _titles(client, "   ") == {"Heat", "Amélie"}
