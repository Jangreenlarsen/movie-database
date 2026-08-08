import pytest

from app.core.config import settings
from app.integrations import plex_client
from app.integrations.plex_client import PlexFetchResult, PlexItem, PlexSectionResult
from app.services import plex_service


@pytest.fixture(autouse=True)
def clear_plex_cache():
    """Feature #88's index er modul-globalt og ville ellers lække mellem
    tests — en test der lægger et fake-bibliotek i cachen ville få den
    næste til at "finde" film der ikke er sat op i den."""
    plex_service.invalidate_cache()
    yield
    plex_service.invalidate_cache()


def _fake_library(items, machine_identifier="abc123", ok=True, error=None):
    return PlexFetchResult(
        ok=ok,
        error=error,
        server_name="Voldby",
        server_version="1.40.0",
        machine_identifier=machine_identifier,
        sections=[
            PlexSectionResult(key="1", title="Film", type="movie", item_count=len(items)),
        ],
        items=items,
    )


def _patch_library(monkeypatch, result):
    async def fake_fetch_library():
        return result

    monkeypatch.setattr(plex_client, "fetch_library", fake_fetch_library)


def _configure(monkeypatch, url="http://192.168.1.50:32400", token="tok"):
    monkeypatch.setattr(settings, "plex_server_url", url)
    monkeypatch.setattr(settings, "plex_token", token)


# --- guid-parsing -----------------------------------------------------------


def test_guid_ids_reads_modern_guid_list():
    item = {"Guid": [{"id": "tmdb://603"}, {"id": "imdb://tt0133093"}]}
    assert plex_client._guid_ids(item) == (603, "tt0133093")


def test_guid_ids_reads_legacy_agent_guid_string():
    """Ældre Plex-agenter har ingen Guid-liste, kun en enkelt guid-streng.
    Feature #45 læste kun listen, så hele legacy-biblioteker faldt usynligt
    tilbage på titel-matchning."""
    item = {"guid": "com.plexapp.agents.imdb://tt0133093?lang=en"}
    assert plex_client._guid_ids(item) == (None, "tt0133093")


def test_guid_ids_reads_legacy_themoviedb_agent():
    item = {"guid": "com.plexapp.agents.themoviedb://603?lang=en"}
    assert plex_client._guid_ids(item) == (603, None)


def test_guid_ids_returns_none_without_any_guid():
    assert plex_client._guid_ids({"title": "Uden guid"}) == (None, None)


# --- titel-normalisering ----------------------------------------------------


def test_normalize_title_strips_accents_punctuation_and_article():
    assert plex_service.normalize_title("The Matrix!") == "matrix"
    assert plex_service.normalize_title("Amélie") == "amelie"
    assert plex_service.normalize_title("  Star   Wars: A New Hope ") == "star wars a new hope"


def test_normalize_title_keeps_danish_letters():
    """æ/ø overlever (de er selvstændige bogstaver, ikke bogstav+accent, så
    NFKD rører dem ikke), mens å dekomponerer til a+ring og ender som "a".
    Uensartet, men harmløst: både vores titler og Plex' går gennem præcis
    samme funktion, så de to sider lander altid samme sted."""
    assert plex_service.normalize_title("Ørkenens Sønner") == "ørkenens sønner"
    assert plex_service.normalize_title("Blå Mænd") == "bla mænd"


def test_normalize_title_handles_none_and_empty():
    assert plex_service.normalize_title(None) == ""
    assert plex_service.normalize_title("   ") == ""


# --- matchning --------------------------------------------------------------


def _index(items):
    return plex_service._build_index(_fake_library(items))


def test_match_prefers_tmdb_id_over_title():
    index = _index(
        [
            PlexItem("movie", "1", "Helt Anden Titel", 1999, 603, None),
            PlexItem("movie", "2", "The Matrix", 1999, None, None),
        ]
    )
    item, matched_by = plex_service._match(index, "movie", 603, "The Matrix", 1999)
    assert (item.rating_key, matched_by) == ("1", "tmdb")


def test_match_falls_back_to_title_and_year():
    index = _index([PlexItem("movie", "2", "The Matrix", 1999, None, None)])
    item, matched_by = plex_service._match(index, "movie", 603, "Matrix", 1999)
    assert (item.rating_key, matched_by) == ("2", "title_year")


def test_match_tolerates_one_year_off():
    """Plex følger ofte den lokale udgivelse, TMDb premieren."""
    index = _index([PlexItem("movie", "2", "The Matrix", 1999, None, None)])
    item, matched_by = plex_service._match(index, "movie", None, "The Matrix", 2000)
    assert (item.rating_key, matched_by) == ("2", "title_year")


def test_match_on_title_alone_only_when_unique():
    index = _index([PlexItem("movie", "7", "Dune", None, None, None)])
    item, matched_by = plex_service._match(index, "movie", None, "Dune", None)
    assert (item.rating_key, matched_by) == ("7", "title")


def test_match_refuses_ambiguous_title():
    """To film med samme titel og ingen årstal må aldrig give et vilkårligt
    af dem — et forkert badge er værre end intet badge."""
    index = _index(
        [
            PlexItem("movie", "1", "Batman", None, None, None),
            PlexItem("movie", "2", "Batman", None, None, None),
        ]
    )
    assert plex_service._match(index, "movie", None, "Batman", None) == (None, None)


def test_match_never_crosses_movie_and_show():
    index = _index([PlexItem("show", "9", "Fargo", 2014, 60622, None)])
    assert plex_service._match(index, "movie", 60622, "Fargo", 2014) == (None, None)


def test_match_returns_none_when_nothing_matches():
    index = _index([PlexItem("movie", "5", "Unrelated", 2010, None, None)])
    assert plex_service._match(index, "movie", 603, "The Matrix", 1999) == (None, None)


# --- play-URL ---------------------------------------------------------------


def test_build_play_url(monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "http://192.168.1.50:32400")
    assert plex_client.build_play_url("42", "abc123") == (
        "http://192.168.1.50:32400/web/index.html#!/server/abc123"
        "/details?key=%2Flibrary%2Fmetadata%2F42"
    )


def test_availability_without_machine_identifier_still_reports_available(monkeypatch):
    """machineIdentifier mangler kun i sjældne proxy-opsætninger. Vi ved
    stadig at filmen er i Plex — badget skal vises, bare uden link."""
    monkeypatch.setattr(settings, "plex_server_url", "http://192.168.1.50:32400")
    index = plex_service._build_index(
        _fake_library([PlexItem("movie", "42", "The Matrix", 1999, 603, None)], machine_identifier=None)
    )
    availability = plex_service._availability(index, "movie", 603, "The Matrix", 1999)
    assert availability.available is True
    assert availability.play_url is None


# --- fetch_library uden konfiguration ---------------------------------------


async def test_fetch_library_reports_what_is_missing(monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")
    result = await plex_client.fetch_library()
    assert result.ok is False
    assert "server-URL" in result.error and "token" in result.error


# --- end-to-end gennem API'et -----------------------------------------------


async def test_availability_endpoint_degrades_when_plex_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")
    await client.post("/api/movies", json={"title": "No Plex Here"})

    response = await client.get("/api/plex/availability?kind=movie")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["ok"] is False
    assert body["items"] == {}
    assert "ikke konfigureret" in body["error"]


async def test_availability_endpoint_maps_library_ids(client, monkeypatch):
    _configure(monkeypatch)
    created = await client.post("/api/movies", json={"title": "The Matrix", "year": 1999})
    movie_id = created.json()["id"]
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    response = await client.get("/api/plex/availability?kind=movie")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["items"][movie_id]["available"] is True
    assert body["items"][movie_id]["matched_by"] == "title_year"
    assert "42" in body["items"][movie_id]["play_url"]


async def test_availability_endpoint_omits_unmatched_movies(client, monkeypatch):
    _configure(monkeypatch)
    await client.post("/api/movies", json={"title": "Findes Ikke I Plex", "year": 2001})
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    body = (await client.get("/api/plex/availability?kind=movie")).json()
    assert body["ok"] is True
    assert body["items"] == {}


async def test_availability_endpoint_surfaces_connection_error(client, monkeypatch):
    _configure(monkeypatch)
    _patch_library(monkeypatch, _fake_library([], ok=False, error="Plex afviste token'et (HTTP 401)"))

    body = (await client.get("/api/plex/availability?kind=movie")).json()
    assert body["configured"] is True
    assert body["ok"] is False
    assert "401" in body["error"]


async def test_availability_uses_cache_until_refresh_is_forced(client, monkeypatch):
    """Ét Plex-hent pr. cache-periode er hele pointen med feature #88 — uden
    det ville hver sideindlæsning trække hele biblioteket igen."""
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "plex_cache_ttl_seconds", 300)
    calls = []

    async def counting_fetch():
        calls.append(1)
        return _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)])

    monkeypatch.setattr(plex_client, "fetch_library", counting_fetch)

    await client.get("/api/plex/availability?kind=movie")
    await client.get("/api/plex/availability?kind=movie")
    assert len(calls) == 1

    await client.post("/api/plex/refresh?kind=movie")
    assert len(calls) == 2


async def test_diagnostics_reports_match_breakdown(client, monkeypatch):
    _configure(monkeypatch)
    await client.post("/api/movies", json={"tmdb_id": None, "title": "The Matrix", "year": 1999})
    await client.post("/api/movies", json={"title": "Ikke I Plex", "year": 2020})
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    response = await client.get("/api/plex/diagnostics")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["server_name"] == "Voldby"
    assert body["library_movie_count"] == 2
    assert body["matched_movies"] == 1
    assert body["matched_by_title"] == 1
    assert [item["title"] for item in body["unmatched_movies"]] == ["Ikke I Plex"]


async def test_diagnostics_explains_missing_configuration(client, monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "tok")

    body = (await client.get("/api/plex/diagnostics")).json()
    assert body["configured"] is False
    assert body["token_configured"] is True
    assert "server-URL" in body["error"]
