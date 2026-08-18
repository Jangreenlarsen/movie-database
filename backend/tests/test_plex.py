import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.integrations import plex_client, tmdb_client
from app.main import app
from app.integrations.plex_client import (
    PlexFetchResult,
    PlexItem,
    PlexSectionResult,
    PlexShowDetails,
)
from app.models.movie import MediaType, MovieFormat
from app.repositories import movie_repository
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
    await client.post("/api/movies", json={"title": "No Plex Here", "media_type": "Fysisk", "format": "F-DVD"})

    response = await client.get("/api/plex/availability?kind=movie")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["ok"] is False
    assert body["items"] == {}
    assert "ikke konfigureret" in body["error"]


async def test_availability_endpoint_maps_library_ids(client, monkeypatch):
    _configure(monkeypatch)
    # Digital, ikke Fysisk — se test_availability_badge_never_shows_on_a_physical_copy
    # for hvorfor det ikke er ligegyldigt hvilken det er her.
    created = await client.post("/api/movies", json={"title": "The Matrix", "year": 1999, "media_type": "Digital", "format": "D-1080"})
    movie_id = created.json()["id"]
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    response = await client.get("/api/plex/availability?kind=movie")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["items"][movie_id]["available"] is True
    assert body["items"][movie_id]["matched_by"] == "title_year"
    assert "42" in body["items"][movie_id]["play_url"]
    # Feature #178 — ingen Shield opsat i denne test, kun en boolean, aldrig
    # selve client-id'et (endpointet er ikke admin-only, se modellens note).
    assert body["shield_configured"] is False


async def test_availability_endpoint_reports_shield_configured(client, monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "plex_shield_client_identifier", "shield-id")
    _patch_library(monkeypatch, _fake_library([]))

    response = await client.get("/api/plex/availability?kind=movie")
    assert response.json()["shield_configured"] is True


async def test_availability_badge_never_shows_on_a_physical_copy(client, monkeypatch):
    """Jans ønske 2026-08-10: en fysisk DVD man også har liggende digitalt i
    Plex skal kunne stå som to separate poster — men badget skal kun vise sig
    på den digitale, aldrig på den fysiske. En fysisk kopi ligger jo netop på
    hylden, ikke i Plex, uanset om samme titel også findes derinde."""
    _configure(monkeypatch)
    created = await client.post(
        "/api/movies", json={"title": "The Matrix", "year": 1999, "media_type": "Fysisk", "format": "F-DVD"}
    )
    movie_id = created.json()["id"]
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    body = (await client.get("/api/plex/availability?kind=movie")).json()
    assert body["ok"] is True
    assert movie_id not in body["items"]


async def test_availability_endpoint_omits_unmatched_movies(client, monkeypatch):
    _configure(monkeypatch)
    await client.post("/api/movies", json={"title": "Findes Ikke I Plex", "year": 2001, "media_type": "Fysisk", "format": "F-DVD"})
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
    # Digital, ikke Fysisk — fysiske poster tælles bevidst ikke med i denne
    # audit (2026-08-10), samme udelukkelse som badget og import-dublet-tjekket.
    await client.post("/api/movies", json={"tmdb_id": None, "title": "The Matrix", "year": 1999, "media_type": "Digital", "format": "D-1080"})
    await client.post("/api/movies", json={"title": "Ikke I Plex", "year": 2020, "media_type": "Digital", "format": "D-1080"})
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


# --- Plex-filter i biblioteks-listen (feature #156) -------------------------


async def test_get_available_ids_returns_none_when_unconfigured(db, monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")
    assert await plex_service.get_available_ids(db, "movie") is None


async def test_get_available_ids_returns_matched_ids(db, monkeypatch):
    _configure(monkeypatch)
    document = await movie_repository.insert(
        db, {"title": "The Matrix", "year": 1999, "is_wishlist": False, "tags": [], "tags_normalized": []}
    )
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    ids = await plex_service.get_available_ids(db, "movie")
    assert ids == {str(document["_id"])}


async def test_movies_plex_filter_only_shows_matched_titles(client, monkeypatch):
    _configure(monkeypatch)
    await client.post("/api/movies", json={"title": "The Matrix", "year": 1999, "media_type": "Digital", "format": "D-1080"})
    await client.post("/api/movies", json={"title": "Ikke På Plex", "year": 2001, "media_type": "Digital", "format": "D-1080"})
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    on_plex = await client.get("/api/movies", params={"plex": "true"})
    assert [m["title"] for m in on_plex.json()["items"]] == ["The Matrix"]

    not_on_plex = await client.get("/api/movies", params={"plex": "false"})
    assert [m["title"] for m in not_on_plex.json()["items"]] == ["Ikke På Plex"]


async def test_tv_shows_plex_filter_only_shows_matched_titles(client, monkeypatch):
    _configure(monkeypatch)
    await client.post("/api/tv-shows", json={"name": "Fargo", "year": 2014, "media_type": "Digital", "format": "D-1080"})
    await client.post("/api/tv-shows", json={"name": "Ikke På Plex", "year": 2001, "media_type": "Digital", "format": "D-1080"})
    _patch_library(monkeypatch, _fake_library([PlexItem("show", "7", "Fargo", 2014, None, None)]))

    on_plex = await client.get("/api/tv-shows", params={"plex": "true"})
    assert [s["name"] for s in on_plex.json()["items"]] == ["Fargo"]


async def test_movies_plex_filter_rejected_when_plex_unconfigured(client, monkeypatch):
    """Feature #156 — bruges filteret uden en konfigureret Plex-server, skal
    det fejle tydeligt (409) i stedet for at vise et vilkårligt tomt/fuldt
    resultat, der ville se ud som om filteret bare "ikke fandt noget"."""
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")

    response = await client.get("/api/movies", params={"plex": "true"})
    assert response.status_code == 409
    assert "ikke konfigureret" in response.json()["detail"]


async def test_tv_shows_plex_filter_rejected_when_plex_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")

    response = await client.get("/api/tv-shows", params={"plex": "true"})
    assert response.status_code == 409


# --- import fra Plex (feature #90) ------------------------------------------


def _patch_create(monkeypatch, created):
    """Fanger hvad importen ville oprette, uden at ramme TMDb. Kun tmdb_id,
    tags og sæsoner er interessante her — resten af oprettelsen er
    movie_service og tv_show_service sit eget ansvar, dækket af deres tests."""
    from app.services import movie_service, tv_show_service

    async def fake_create_movie(db, payload, registered_by):
        created.append(("movie", payload.tmdb_id, payload.tags))

    async def fake_create_tv_show(db, payload, registered_by):
        created.append(("show", payload.tmdb_id, payload.tags, payload.owned_seasons))

    monkeypatch.setattr(movie_service, "create_movie", fake_create_movie)
    monkeypatch.setattr(tv_show_service, "create_tv_show", fake_create_tv_show)


async def test_import_requires_plex_configuration(client, monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")

    body = (await client.post("/api/plex/import", json={"dry_run": True})).json()
    assert body["ok"] is False
    assert "ikke konfigureret" in body["error"]


async def test_import_requires_tmdb_token_before_looping(client, monkeypatch):
    """CLAUDE.md regel 16 — en manglende nøgle rammer hele batchen og skal
    meldes én gang, ikke som N identiske fejl."""
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "tmdb_api_token", "")
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "1", "The Matrix", 1999, 603, None, resolution="1080")]))

    body = (await client.post("/api/plex/import", json={"dry_run": True})).json()
    assert body["ok"] is False
    assert "TMDb-token" in body["error"]
    assert body["imported"] == []


async def test_import_dry_run_creates_nothing(client, monkeypatch):
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "1", "The Matrix", 1999, 603, None, resolution="1080")]))

    body = (await client.post("/api/plex/import", json={"dry_run": True})).json()
    assert body["ok"] is True
    assert body["dry_run"] is True
    assert [item["title"] for item in body["imported"]] == ["The Matrix"]
    assert body["imported"][0]["resolved_via"] == "plex_guid"
    assert created == []


async def test_import_creates_with_tag(client, monkeypatch):
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "1", "The Matrix", 1999, 603, None, resolution="1080")]))

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert body["ok"] is True
    assert created == [("movie", 603, ["Plex-import"])]
    assert len(body["imported"]) == 1


async def test_import_skips_what_we_already_have_digitally(client, monkeypatch):
    """Genbruger feature #88s matchning i modsat retning — en digital film vi
    allerede har på titel+år må ikke importeres igen bare fordi Plex har et
    tmdb-id, ellers ville hver importkørsel oprette endnu en dublet."""
    _configure(monkeypatch)
    await client.post("/api/movies", json={"title": "The Matrix", "year": 1999, "media_type": "Digital", "format": "D-1080"})
    created = []
    _patch_create(monkeypatch, created)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "1", "The Matrix", 1999, 603, None, resolution="1080")]))

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert body["already_present"] == 1
    assert body["imported"] == []
    assert created == []


async def test_import_does_not_skip_when_only_a_physical_copy_exists(client, monkeypatch):
    """Jans ønske 2026-08-10: en fysisk DVD man allerede har registreret må
    ikke blokere den digitale Plex-udgave af samme titel fra at blive
    importeret — man skal kunne have begge som separate poster. Før denne
    rettelse blev enhver eksisterende post (uanset medietype) talt som
    "har den allerede", så en fysisk kopi stille og roligt forhindrede den
    digitale i nogensinde at nå ind i portalen."""
    _configure(monkeypatch)
    await client.post("/api/movies", json={"title": "The Matrix", "year": 1999, "media_type": "Fysisk", "format": "F-DVD"})
    created = []
    _patch_create(monkeypatch, created)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "1", "The Matrix", 1999, 603, None, resolution="1080")]))

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert body["already_present"] == 0
    assert created == [("movie", 603, ["Plex-import"])]
    assert len(body["imported"]) == 1


async def test_import_resolves_missing_tmdb_id_via_search(client, monkeypatch):
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)

    async def fake_search_movies(query):
        return [{"tmdb_id": 603, "title": "The Matrix", "year": 1999}]

    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "1", "The Matrix", 1999, None, None, resolution="1080")]))

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert created == [("movie", 603, ["Plex-import"])]
    assert body["imported"][0]["resolved_via"] == "tmdb_search"


async def test_import_refuses_ambiguous_search_result(client, monkeypatch):
    """Jans valg 2026-08-08: hellere rapportere titlen end lade et gæt blive
    til data der ser lige så rigtig ud som resten af biblioteket."""
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)

    async def fake_search_movies(query):
        return [
            {"tmdb_id": 1, "title": "Batman", "year": 1989},
            {"tmdb_id": 2, "title": "Batman", "year": 1989},
        ]

    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "1", "Batman", 1989, None, None, resolution="1080")]))

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert created == []
    assert [item["title"] for item in body["unmatched"]] == ["Batman"]


async def test_import_refuses_search_result_with_wrong_year(client, monkeypatch):
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)

    async def fake_search_movies(query):
        return [{"tmdb_id": 99, "title": "The Matrix", "year": 2021}]

    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "1", "The Matrix", 1999, None, None, resolution="1080")]))

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert created == []
    assert len(body["unmatched"]) == 1


async def test_import_marks_seasons_owned_from_plex(client, monkeypatch):
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)

    async def fake_fetch_show_details(rating_key):
        return PlexShowDetails(seasons=[1, 2, 3], resolution="1080")

    monkeypatch.setattr(plex_client, "fetch_show_details", fake_fetch_show_details)
    _patch_library(monkeypatch, _fake_library([PlexItem("show", "7", "Fargo", 2014, 60622, None)]))

    await client.post("/api/plex/import", json={"dry_run": False})
    assert created == [("show", 60622, ["Plex-import"], [1, 2, 3])]


async def test_import_can_limit_to_movies_only(client, monkeypatch):
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)
    _patch_library(
        monkeypatch,
        _fake_library(
            [
                PlexItem("movie", "1", "The Matrix", 1999, 603, None, resolution="1080"),
                PlexItem("show", "7", "Fargo", 2014, 60622, None),
            ]
        ),
    )

    await client.post("/api/plex/import", json={"dry_run": False, "include_shows": False})
    assert [entry[0] for entry in created] == ["movie"]


async def test_import_stops_immediately_on_rate_limit(client, monkeypatch):
    """CLAUDE.md regel 16 — bliv ikke ved med at ramme en allerede-throttlet
    API for resten af batchen."""
    from app.core.errors import TmdbRateLimitedError
    from app.services import movie_service

    _configure(monkeypatch)
    calls = []

    async def rate_limited_create(db, payload, registered_by):
        calls.append(payload.tmdb_id)
        raise TmdbRateLimitedError()

    monkeypatch.setattr(movie_service, "create_movie", rate_limited_create)
    _patch_library(
        monkeypatch,
        _fake_library(
            [
                PlexItem("movie", "1", "Film A", 2001, 1, None, resolution="1080"),
                PlexItem("movie", "2", "Film B", 2002, 2, None, resolution="1080"),
                PlexItem("movie", "3", "Film C", 2003, 3, None, resolution="1080"),
            ]
        ),
    )

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert body["stopped_early"] is True
    # Stoppede efter den første — prøvede ikke de to andre.
    assert calls == [1]


async def test_import_empty_tag_creates_without_tag(client, monkeypatch):
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "1", "The Matrix", 1999, 603, None, resolution="1080")]))

    await client.post("/api/plex/import", json={"dry_run": False, "tag": "   "})
    assert created == [("movie", 603, [])]


# --- medietype og format ud fra opløsning (feature #91) ---------------------


def test_format_for_resolution_maps_plex_values():
    assert plex_service.format_for_resolution("4k") == MovieFormat.DIGITAL_UHD
    assert plex_service.format_for_resolution("2160") == MovieFormat.DIGITAL_UHD
    assert plex_service.format_for_resolution("1080") == MovieFormat.DIGITAL_HD
    # v0.105.0 — 720 fik sit eget trin (D-720).
    assert plex_service.format_for_resolution("720") == MovieFormat.DIGITAL_720
    assert plex_service.format_for_resolution("576") == MovieFormat.DIGITAL_STD
    assert plex_service.format_for_resolution("480") == MovieFormat.DIGITAL_STD
    assert plex_service.format_for_resolution("sd") == MovieFormat.DIGITAL_STD


def test_format_for_resolution_handles_suffixed_and_odd_values():
    assert plex_service.format_for_resolution("1080p") == MovieFormat.DIGITAL_HD
    assert plex_service.format_for_resolution(" 4K ") == MovieFormat.DIGITAL_UHD
    # Ukendt streng må ikke gætte et format på plads.
    assert plex_service.format_for_resolution("mystisk") is None
    assert plex_service.format_for_resolution(None) is None
    assert plex_service.format_for_resolution("") is None


def test_dominant_resolution_picks_most_common_not_highest():
    """Ét 4K-afsnit ud af mange gør ikke serien til en UHD-udgave."""
    assert plex_client._dominant_resolution(["1080", "1080", "1080", "4k"]) == "1080"


def test_dominant_resolution_breaks_tie_towards_higher_quality():
    assert plex_client._dominant_resolution(["1080", "4k"]) == "4k"
    assert plex_client._dominant_resolution(["480", "1080"]) == "1080"


def test_dominant_resolution_without_data():
    assert plex_client._dominant_resolution([]) is None


def test_resolution_read_from_first_media_entry():
    assert plex_client._resolution({"Media": [{"videoResolution": "4k"}]}) == "4k"
    # Første post uden opløsning skal ikke skygge for en senere der har en.
    assert plex_client._resolution({"Media": [{}, {"videoResolution": "1080"}]}) == "1080"
    assert plex_client._resolution({}) is None
    assert plex_client._resolution({"Media": []}) is None


async def test_import_sets_digital_media_type_and_format_from_resolution(client, monkeypatch):
    _configure(monkeypatch)
    captured = []
    from app.services import movie_service

    async def fake_create_movie(db, payload, registered_by):
        captured.append((payload.media_type, payload.format))

    monkeypatch.setattr(movie_service, "create_movie", fake_create_movie)
    _patch_library(
        monkeypatch,
        _fake_library([PlexItem("movie", "1", "The Matrix", 1999, 603, None, resolution="4k")]),
    )

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert captured == [(MediaType.DIGITAL, MovieFormat.DIGITAL_UHD)]
    assert body["imported"][0]["format"] == "D-4K"


async def test_import_preview_shows_movie_format_without_creating(client, monkeypatch):
    """Filmens opløsning står allerede i sektions-listen, så formatet kan
    vises i forhåndsvisningen uden et eneste ekstra kald."""
    _configure(monkeypatch)
    _patch_library(
        monkeypatch,
        _fake_library([PlexItem("movie", "1", "Gammel Film", 1975, 11, None, resolution="480")]),
    )

    body = (await client.post("/api/plex/import", json={"dry_run": True})).json()
    assert body["imported"][0]["format"] == "D-480"


async def test_import_falls_back_to_hd_when_resolution_is_unknown(client, monkeypatch):
    """BUGS.md #52 — kan Plex ikke oplyse opløsningen, importeres elementet
    alligevel med fallback-formatet og markeres som sådan. Før blev det
    sprunget over, hvilket betød at en hel kategori stiltiende aldrig nåede
    ind i portalen."""
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)
    _patch_library(
        monkeypatch,
        _fake_library([PlexItem("movie", "1", "Uden Opløsning", 2000, 12, None)]),
    )

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert created == [("movie", 12, ["Plex-import"])]
    assert body["unmatched"] == []
    assert body["imported"][0]["format"] == "D-1080"
    assert body["imported"][0]["format_is_fallback"] is True


async def test_import_show_falls_back_to_hd_when_episodes_have_no_resolution(client, monkeypatch):
    """Serier rammes hårdest af den manglende opløsning: den kræver et ekstra
    kald pr. serie, og enhver fejl der ville før koste hele importen af
    serien."""
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)

    async def fake_fetch_show_details(rating_key):
        return PlexShowDetails(seasons=[1], resolution=None)

    monkeypatch.setattr(plex_client, "fetch_show_details", fake_fetch_show_details)
    _patch_library(monkeypatch, _fake_library([PlexItem("show", "7", "Fargo", 2014, 60622, None)]))

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert created == [("show", 60622, ["Plex-import"], [1])]
    assert body["unmatched"] == []


async def test_known_resolution_is_not_marked_as_fallback(client, monkeypatch):
    _configure(monkeypatch)
    created = []
    _patch_create(monkeypatch, created)
    _patch_library(
        monkeypatch,
        _fake_library([PlexItem("movie", "1", "Skarp Film", 2000, 12, None, resolution="4k")]),
    )

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert body["imported"][0]["format"] == "D-4K"
    assert body["imported"][0]["format_is_fallback"] is False


async def test_import_show_takes_format_and_seasons_from_episodes(client, monkeypatch):
    _configure(monkeypatch)
    captured = []
    from app.services import tv_show_service

    async def fake_create_tv_show(db, payload, registered_by):
        captured.append((payload.media_type, payload.format, payload.owned_seasons))

    async def fake_fetch_show_details(rating_key):
        return PlexShowDetails(seasons=[1, 2], resolution="1080")

    monkeypatch.setattr(tv_show_service, "create_tv_show", fake_create_tv_show)
    monkeypatch.setattr(plex_client, "fetch_show_details", fake_fetch_show_details)
    _patch_library(monkeypatch, _fake_library([PlexItem("show", "7", "Fargo", 2014, 60622, None)]))

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert captured == [(MediaType.DIGITAL, MovieFormat.DIGITAL_HD, [1, 2])]
    assert body["imported"][0]["format"] == "D-1080"



def _patch_tmdb_details(monkeypatch, title="The Matrix", year=1999):
    """Rigtig oprettelse gennem movie_service, men uden at ramme TMDb —
    rundtur-testene skal bruge et faktisk gemt dokument at slå op på."""

    async def fake_get_movie_details(tmdb_id):
        return {
            "tmdb_id": tmdb_id,
            "title": title,
            "year": year,
            "poster_url": None,
            "overview": None,
            "genres": [],
            "cast": [],
            "director": None,
            "rating": None,
            "runtime": None,
            "imdb_url": None,
            "trailer_url": None,
            "collection_id": None,
            "collection_name": None,
        }

    monkeypatch.setattr(tmdb_client, "get_movie_details", fake_get_movie_details)


async def test_imported_movie_is_afterwards_reported_as_available(client, monkeypatch):
    """Rundtur: importér fra Plex, og slå derefter tilgængeligheden op.

    En film der lige er importeret FRA Plex må aldrig bagefter rapporteres
    som "ikke fundet i Plex" — det er selvmodsigende og var Jans fejlmelding
    2026-08-08."""
    _configure(monkeypatch)
    _patch_tmdb_details(monkeypatch)
    _patch_library(
        monkeypatch,
        _fake_library([PlexItem("movie", "42", "The Matrix", 1999, 603, None, resolution="4k")]),
    )

    import_body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert len(import_body["imported"]) == 1, import_body

    listed = await client.get("/api/movies")
    movie_id = listed.json()["items"][0]["id"]

    availability = (await client.get("/api/plex/availability?kind=movie")).json()
    assert availability["ok"] is True
    assert movie_id in availability["items"], availability
    assert availability["items"][movie_id]["available"] is True


async def test_imported_movie_resolved_via_search_is_also_available(client, monkeypatch):
    """Samme rundtur for et Plex-element uden TMDb-id, hvor importen selv
    fandt id'et via en titel-søgning. Badget kan her ikke matche på id —
    Plex-siden har intet — så det må klare sig på titel og år."""
    _configure(monkeypatch)

    async def fake_search_movies(query):
        return [{"tmdb_id": 603, "title": "The Matrix", "year": 1999}]

    monkeypatch.setattr(tmdb_client, "search_movies", fake_search_movies)
    _patch_tmdb_details(monkeypatch)
    _patch_library(
        monkeypatch,
        _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None, resolution="1080")]),
    )

    import_body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert len(import_body["imported"]) == 1, import_body

    listed = await client.get("/api/movies")
    movie_id = listed.json()["items"][0]["id"]

    availability = (await client.get("/api/plex/availability?kind=movie")).json()
    assert movie_id in availability["items"], availability


# --- ufuldstændig hentning (BUGS.md #51) ------------------------------------


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _install_fake_http(monkeypatch, responses):
    """Erstatter plex_client._client med en klient der svarer efter `responses`
    (en dict fra sti-fragment til _FakeResponse eller en exception)."""

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None, params=None, timeout=None):
            # Præcis URL-match, ikke delstreng: rod-URLen er et præfiks af
            # alle de øvrige og ville ellers svare på dem alle.
            response = responses.get(url)
            if response is None:
                raise AssertionError(f"uventet URL i test: {url}")
            if isinstance(response, Exception):
                raise response
            return response

    monkeypatch.setattr(plex_client, "_client", lambda: FakeClient())


BASE = "http://192.168.1.50:32400"


def _identity_and_sections():
    return {
        BASE + "/": _FakeResponse(
            {"MediaContainer": {"friendlyName": "Voldby", "version": "1.40", "machineIdentifier": "abc"}}
        ),
        BASE + "/library/sections": _FakeResponse(
            {"MediaContainer": {"Directory": [{"key": "1", "title": "Film", "type": "movie"}]}}
        ),
    }


async def test_fetch_library_fails_when_a_page_errors(monkeypatch):
    """Før BUGS.md #51 returnerede en fejl undervejs den delvise liste som om
    den var hele biblioteket — og filmene der manglede blev rapporteret som
    "ikke fundet i Plex" selvom de lå der."""
    _configure(monkeypatch)
    responses = _identity_and_sections()
    responses[BASE + "/library/sections/1/all"] = _FakeResponse({}, status_code=500)
    _install_fake_http(monkeypatch, responses)

    result = await plex_client.fetch_library()
    assert result.ok is False
    assert "ufuldstændigt" in result.error or "fuldstændigt" in result.error


async def test_fetch_library_fails_when_count_does_not_match_total_size(monkeypatch):
    """Plex oplyser sektionens fulde størrelse på hver side. Får vi færre
    elementer end lovet, er hentningen afkortet — også selvom hver enkelt
    forespørgsel svarede 200."""
    _configure(monkeypatch)
    responses = _identity_and_sections()
    responses[BASE + "/library/sections/1/all"] = _FakeResponse(
        {
            "MediaContainer": {
                "totalSize": 40,
                "Metadata": [
                    {"ratingKey": "1", "title": "Kun Én Film", "year": 2001},
                ],
            }
        }
    )
    _install_fake_http(monkeypatch, responses)

    result = await plex_client.fetch_library()
    assert result.ok is False
    assert "40" in result.error


async def test_fetch_library_succeeds_when_count_matches(monkeypatch):
    _configure(monkeypatch)
    responses = _identity_and_sections()
    responses[BASE + "/library/sections/1/all"] = _FakeResponse(
        {
            "MediaContainer": {
                "totalSize": 1,
                "Metadata": [{"ratingKey": "1", "title": "Den Ene Film", "year": 2001}],
            }
        }
    )
    _install_fake_http(monkeypatch, responses)

    result = await plex_client.fetch_library()
    assert result.ok is True
    assert [item.title for item in result.items] == ["Den Ene Film"]


async def test_availability_reports_error_instead_of_empty_when_fetch_failed(client, monkeypatch):
    """Kernen i fejlmeldingen: en mislykket hentning må ikke se ud som
    "intet ligger i Plex" — så ville hver eneste film få "Ikke fundet i
    Plex" uden at noget forklarede hvorfor."""
    _configure(monkeypatch)
    _patch_tmdb_details(monkeypatch)
    await client.post(
        "/api/movies",
        json={"title": "The Matrix", "year": 1999, "media_type": "Fysisk", "format": "F-DVD"},
    )
    _patch_library(monkeypatch, _fake_library([], ok=False, error="Plex-biblioteket kunne ikke hentes fuldstændigt"))

    body = (await client.get("/api/plex/availability?kind=movie")).json()
    assert body["ok"] is False
    assert body["error"]
    assert body["items"] == {}


def _patch_tv_details(monkeypatch, name="Fargo"):
    async def fake_get_tv_show_details(tv_id):
        return {
            "tmdb_id": tv_id,
            "name": name,
            "year": 2014,
            "end_year": None,
            "status": "Ended",
            "poster_url": None,
            "overview": None,
            "genres": [],
            "cast": [],
            "creators": [],
            "rating": None,
            "number_of_seasons": 2,
            "number_of_episodes": 20,
            "imdb_url": None,
            "seasons": [
                {"season_number": 1, "name": "Sæson 1", "episode_count": 10},
                {"season_number": 2, "name": "Sæson 2", "episode_count": 10},
            ],
        }

    monkeypatch.setattr(tmdb_client, "get_tv_show_details", fake_get_tv_show_details)


async def test_imported_tv_show_appears_under_tv_shows(client, monkeypatch):
    """Jans fejlmelding 2026-08-08: TV-serier importeret fra Plex dukkede
    ikke op under TV-serier. Rundtur: importér en serie, og hent derefter
    TV-listen."""
    _configure(monkeypatch)
    _patch_tv_details(monkeypatch)

    async def fake_fetch_show_details(rating_key):
        return PlexShowDetails(seasons=[1, 2], resolution="1080")

    monkeypatch.setattr(plex_client, "fetch_show_details", fake_fetch_show_details)
    _patch_library(monkeypatch, _fake_library([PlexItem("show", "7", "Fargo", 2014, 60622, None)]))

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    assert body["ok"] is True, body
    assert len(body["imported"]) == 1, body

    listed = (await client.get("/api/tv-shows")).json()
    assert [show["name"] for show in listed["items"]] == ["Fargo"]


async def test_show_without_episode_resolution_still_reaches_tv_shows(client, monkeypatch):
    """BUGS.md #52 — Jans fejlmelding. Kunne opløsningen ikke afgøres, blev
    serien før slet ikke oprettet, og dukkede derfor aldrig op under
    TV-serier. Nu importeres den med fallback-formatet."""
    _configure(monkeypatch)
    _patch_tv_details(monkeypatch)

    async def fake_fetch_show_details(rating_key):
        return PlexShowDetails(seasons=[1], resolution=None)

    monkeypatch.setattr(plex_client, "fetch_show_details", fake_fetch_show_details)
    _patch_library(monkeypatch, _fake_library([PlexItem("show", "7", "Fargo", 2014, 60622, None)]))

    body = (await client.post("/api/plex/import", json={"dry_run": False})).json()
    listed = (await client.get("/api/tv-shows")).json()

    assert body["unmatched"] == []
    assert [show["name"] for show in listed["items"]] == ["Fargo"]
    assert listed["items"][0]["format"] == "D-1080"


async def test_dry_run_preview_includes_tv_shows(client, monkeypatch):
    """Forhåndsvisningen må ikke udelade serier — så ville man tro at der
    intet var at importere."""
    _configure(monkeypatch)
    _patch_library(monkeypatch, _fake_library([PlexItem("show", "7", "Fargo", 2014, 60622, None)]))

    body = (await client.post("/api/plex/import", json={"dry_run": True})).json()
    assert [item["title"] for item in body["imported"]] == ["Fargo"]
    assert body["imported"][0]["kind"] == "show"


# --- feature #178: afspil på Shield TV ---------------------------------------


class _RecordedResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


class _RecordingPlexClient:
    """Erstatning for `plex_client._client()` — undgår en ny testafhængighed
    (respx/MockTransport) for det par lav-niveau HTTP-formaterings-tests
    nedenfor, der er de eneste i denne fil som rent faktisk skal kunne se den
    *nøjagtige* URL/header/param-konstruktion (regel 19: en forkert
    Companion-kommando ville fejle stille mod Jans rigtige Shield)."""

    def __init__(self, responder):
        self._responder = responder
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None, params=None):
        self.calls.append({"url": url, "headers": headers, "params": params})
        return self._responder(url, headers, params)


async def test_fetch_clients_parses_server_list(monkeypatch):
    _configure(monkeypatch)
    fake = _RecordingPlexClient(
        lambda url, headers, params: _RecordedResponse(
            200,
            {
                "MediaContainer": {
                    "Server": [
                        {"name": "Shield", "machineIdentifier": "shield-id", "product": "Plex for Android (TV)"},
                        {"name": "Uden id"},  # mangler machineIdentifier — skal springes over
                    ]
                }
            },
        )
    )
    monkeypatch.setattr(plex_client, "_client", lambda: fake)

    clients, raw_count, error = await plex_client.fetch_clients()
    assert error is None
    assert len(clients) == 1
    assert clients[0].name == "Shield"
    assert clients[0].machine_identifier == "shield-id"
    assert fake.calls[0]["url"].endswith("/clients")
    # BUGS.md #76 — det samlede antal PMS rapporterede (2), ikke kun de
    # brugbare (1), så en admin kan se om noget blev filtreret fra.
    assert raw_count == 2


async def test_fetch_clients_reports_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")

    clients, raw_count, error = await plex_client.fetch_clients()
    assert clients == []
    assert raw_count == 0
    assert "ikke konfigureret" in error


async def test_fetch_clients_reports_raw_count_even_when_all_are_filtered_out(monkeypatch):
    """BUGS.md #76 — reproducerer netop det tilfælde 'raw_entry_count' findes
    for: PMS rapporterer entries, men ingen har et brugbart client-id."""
    _configure(monkeypatch)
    fake = _RecordingPlexClient(
        lambda url, headers, params: _RecordedResponse(
            200, {"MediaContainer": {"Server": [{"name": "Uden id"}, {"name": "Også uden id"}]}}
        )
    )
    monkeypatch.setattr(plex_client, "_client", lambda: fake)

    clients, raw_count, error = await plex_client.fetch_clients()
    assert error is None
    assert clients == []
    assert raw_count == 2


async def test_play_on_client_sends_the_correct_companion_command(monkeypatch):
    _configure(monkeypatch, url="http://192.168.1.50:32400", token="tok")
    fake = _RecordingPlexClient(lambda url, headers, params: _RecordedResponse(200))
    monkeypatch.setattr(plex_client, "_client", lambda: fake)

    ok, message = await plex_client.play_on_client(
        rating_key="42", server_machine_identifier="server-id", client_identifier="shield-id"
    )

    assert ok is True
    call = fake.calls[0]
    assert call["url"] == "http://192.168.1.50:32400/player/playback/playMedia"
    assert call["headers"]["X-Plex-Target-Client-Identifier"] == "shield-id"
    assert call["params"]["key"] == "/library/metadata/42"
    assert call["params"]["machineIdentifier"] == "server-id"
    assert call["params"]["address"] == "192.168.1.50"
    assert call["params"]["port"] == "32400"
    assert call["params"]["token"] == "tok"
    # Jan, opfølgning 2026-08-18: undgå transcoding — se play_on_client's
    # docstring for hvorfor dette ikke er en garanti, kun et forsøg.
    assert call["params"]["directPlay"] == "1"
    assert call["params"]["directStream"] == "1"


async def test_play_on_client_reports_a_readable_error_when_the_shield_is_unreachable(monkeypatch):
    """404 er PMS' egen "klienten findes ikke lige nu"-svar — typisk fordi
    Plex-appen ikke er åben på Shielden. En admin/gæst der trykker knappen
    skal se hvorfor, ikke en rå HTTP-status."""
    _configure(monkeypatch)
    fake = _RecordingPlexClient(lambda url, headers, params: _RecordedResponse(404))
    monkeypatch.setattr(plex_client, "_client", lambda: fake)

    ok, message = await plex_client.play_on_client("42", "server-id", "shield-id")
    assert ok is False
    assert "Plex-appen" in message


async def test_play_on_shield_requires_the_shield_to_be_configured_first(client, monkeypatch):
    _configure(monkeypatch)
    created = await client.post(
        "/api/movies", json={"title": "The Matrix", "year": 1999, "media_type": "Digital", "format": "D-1080"}
    )
    movie_id = created.json()["id"]

    response = await client.post(
        "/api/plex/play-on-shield", json={"kind": "movie", "item_id": movie_id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "ikke konfigureret endnu" in body["message"]


async def test_play_on_shield_end_to_end_through_the_api(client, monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "plex_shield_client_identifier", "shield-id")
    created = await client.post(
        "/api/movies", json={"title": "The Matrix", "year": 1999, "media_type": "Digital", "format": "D-1080"}
    )
    movie_id = created.json()["id"]
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    async def fake_play_on_client(rating_key, server_machine_identifier, client_identifier):
        assert rating_key == "42"
        assert client_identifier == "shield-id"
        return True, "Afspilning startet på Shield TV."

    monkeypatch.setattr(plex_client, "play_on_client", fake_play_on_client)

    response = await client.post(
        "/api/plex/play-on-shield", json={"kind": "movie", "item_id": movie_id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "Shield" in body["message"]


async def test_play_on_shield_reports_when_the_title_is_not_in_plex(client, monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "plex_shield_client_identifier", "shield-id")
    created = await client.post(
        "/api/movies", json={"title": "Findes Ikke I Plex", "year": 2001, "media_type": "Digital", "format": "D-1080"}
    )
    movie_id = created.json()["id"]
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    response = await client.post(
        "/api/plex/play-on-shield", json={"kind": "movie", "item_id": movie_id}
    )
    body = response.json()
    assert body["ok"] is False
    assert "Findes ikke i Plex" in body["message"]


async def test_play_on_shield_works_for_tv_shows_too(client, monkeypatch):
    """Regel 16 — "regler der kun gælder én gren": en test der kun dækker
    film ville kunne lade TV-serie-vejen stiltiende mangle `kind`-håndtering."""
    _configure(monkeypatch)
    monkeypatch.setattr(settings, "plex_shield_client_identifier", "shield-id")
    created = await client.post(
        "/api/tv-shows", json={"name": "Fargo", "year": 2014, "media_type": "Digital", "format": "D-1080"}
    )
    show_id = created.json()["id"]
    _patch_library(monkeypatch, _fake_library([PlexItem("show", "7", "Fargo", 2014, None, None)]))

    async def fake_play_on_client(rating_key, server_machine_identifier, client_identifier):
        assert rating_key == "7"
        return True, "Afspilning startet på Shield TV."

    monkeypatch.setattr(plex_client, "play_on_client", fake_play_on_client)

    response = await client.post(
        "/api/plex/play-on-shield", json={"kind": "show", "item_id": show_id}
    )
    assert response.json()["ok"] is True


async def test_clients_endpoint_admin_only(client, monkeypatch):
    """`client`-fixturen er den allerførste registrerede bruger og dermed
    allerede admin (feature #175's bootstrap-undtagelse) — endpointet skal
    derfor virke for den, men afvise en almindelig standard-bruger."""
    _configure(monkeypatch)
    fake = _RecordingPlexClient(
        lambda url, headers, params: _RecordedResponse(200, {"MediaContainer": {"Server": []}})
    )
    monkeypatch.setattr(plex_client, "_client", lambda: fake)

    admin_response = await client.get("/api/plex/clients")
    assert admin_response.status_code == 200

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        register = await standard_client.post(
            "/api/auth/register", json={"username": "notadmin178", "password": "testpassword123"}
        )
        await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})
        await client.patch(f"/api/users/{register.json()['id']}/role", json={"role": "standard"})

        response = await standard_client.get("/api/plex/clients")
        assert response.status_code == 403


async def test_clients_endpoint_surfaces_the_raw_count(client, monkeypatch):
    """BUGS.md #76 — end-to-end: en admin skal kunne se PMS' egen rapporterede
    totalantal via API-svaret, ikke kun den filtrerede `items`-liste."""
    _configure(monkeypatch)
    fake = _RecordingPlexClient(
        lambda url, headers, params: _RecordedResponse(
            200, {"MediaContainer": {"Server": [{"name": "Uden id"}]}}
        )
    )
    monkeypatch.setattr(plex_client, "_client", lambda: fake)

    response = await client.get("/api/plex/clients")
    body = response.json()
    assert body["items"] == []
    assert body["raw_entry_count"] == 1


async def test_system_settings_returns_the_shield_client_identifier_plainly(client, monkeypatch):
    """Ikke en hemmelighed (CLAUDE.md regel 6-undtagelsen, samme som
    plex_server_url) — skal derfor komme med sin faktiske værdi, ikke kun
    configured/source."""
    monkeypatch.setattr(settings, "plex_shield_client_identifier", "shield-id")

    response = await client.get("/api/settings/system")
    assert response.json()["plex_shield_client_identifier"] == "shield-id"


# --- feature #178-opfølgning: start/stop-toggle -------------------------------


async def test_stop_client_sends_the_correct_companion_command(monkeypatch):
    _configure(monkeypatch, url="http://192.168.1.50:32400", token="tok")
    fake = _RecordingPlexClient(lambda url, headers, params: _RecordedResponse(200))
    monkeypatch.setattr(plex_client, "_client", lambda: fake)

    ok, message = await plex_client.stop_client("shield-id")

    assert ok is True
    call = fake.calls[0]
    assert call["url"] == "http://192.168.1.50:32400/player/playback/stop"
    assert call["headers"]["X-Plex-Target-Client-Identifier"] == "shield-id"
    assert "stoppet" in message.lower()


async def test_stop_client_reports_a_readable_error_when_the_shield_is_unreachable(monkeypatch):
    _configure(monkeypatch)
    fake = _RecordingPlexClient(lambda url, headers, params: _RecordedResponse(404))
    monkeypatch.setattr(plex_client, "_client", lambda: fake)

    ok, message = await plex_client.stop_client("shield-id")
    assert ok is False
    assert "Plex-appen" in message


async def test_stop_shield_requires_the_shield_to_be_configured_first(client):
    response = await client.post("/api/plex/stop-shield")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "ikke konfigureret endnu" in body["message"]


async def test_stop_shield_end_to_end_through_the_api(client, monkeypatch):
    monkeypatch.setattr(settings, "plex_shield_client_identifier", "shield-id")

    async def fake_stop_client(client_identifier):
        assert client_identifier == "shield-id"
        return True, "Afspilning stoppet på Shield TV."

    monkeypatch.setattr(plex_client, "stop_client", fake_stop_client)

    response = await client.post("/api/plex/stop-shield")
    body = response.json()
    assert body["ok"] is True
    assert "stoppet" in body["message"].lower()
