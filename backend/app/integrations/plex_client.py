"""Plex Media Server-integration (feature #45, omskrevet i feature #88).

Feature #45 slog én film op ad gangen via `/search?query=...`, udløst af en
manuel "Tjek Plex"-knap. Feature #88 vendte det om: portalen afgør selv om
noget ligger i Plex, for hele biblioteket på én gang. Det kræver en anden
adgangsform — hele Plex-bibliotekets index hentes i ét hug pr. sektion
(`/library/sections/{key}/all`) og matches lokalt — for ellers ville en
biblioteksside med 200 kort udløse 200 søgekald mod Plex.

Alle funktioner her er best-effort: en manglende, utilgængelig eller
fejlkonfigureret Plex-server degraderer til "ingen data" med en læsbar
fejlbesked, aldrig til en exception der vælter biblioteksvisningen — samme
filosofi som UPC/Discogs-opslagene (MOVIE_API_REFERENCE.md).
"""

import logging
import re
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

logger = logging.getLogger("moviedb")

# Plex svarer normalt inden for få hundrede ms på LAN, men `/all` på en stor
# sektion (>5000 elementer) kan tage flere sekunder. Rundhåndet, fordi
# alternativet er et falsk "Plex utilgængelig" på et bibliotek der bare er
# stort — kaldet sker alligevel højst én gang pr. cache-TTL.
FETCH_TIMEOUT = 30
IDENTITY_TIMEOUT = 10

# Plex' /library/sections/{key}/all er upagineret som standard, men serveren
# kan afvise meget store svar. Vi henter i sider via Plex' egne
# range-headere, så et stort bibliotek ikke rammer et ukendt loft.
PAGE_SIZE = 500
MAX_PAGES = 40  # 20.000 elementer pr. sektion — langt over enhver hjemmeserver


@dataclass
class PlexItem:
    """Ét element fra Plex, reduceret til det matchning har brug for."""

    kind: str  # "movie" | "show"
    rating_key: str
    title: str
    year: int | None
    tmdb_id: int | None
    imdb_id: str | None


@dataclass
class PlexSectionResult:
    key: str
    title: str
    type: str
    item_count: int = 0
    with_tmdb_guid: int = 0
    with_imdb_guid: int = 0


@dataclass
class PlexFetchResult:
    """Udfaldet af ét fuldt biblioteks-hent. `ok=False` betyder at intet kan
    matches — `error` er så den besked der vises til admin i fejlsøgningen."""

    ok: bool
    error: str | None = None
    server_name: str | None = None
    server_version: str | None = None
    machine_identifier: str | None = None
    sections: list[PlexSectionResult] = field(default_factory=list)
    items: list[PlexItem] = field(default_factory=list)


def is_configured() -> bool:
    return bool(settings.plex_server_url and settings.plex_token)


def _base_url() -> str:
    return settings.plex_server_url.rstrip("/")


def _headers() -> dict:
    return {"X-Plex-Token": settings.plex_token, "Accept": "application/json"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=FETCH_TIMEOUT, verify=settings.plex_verify_ssl)


def _guid_ids(item: dict) -> tuple[int | None, str | None]:
    """Trækker TMDb- og IMDb-id ud af et Plex-element.

    To formater skal håndteres, fordi Plex' guid-repræsentation afhænger af
    hvilken *agent* sektionen bruger:
      - Nyere agenter ("Plex Movie", "Plex TV Series") giver en `Guid`-liste
        med `tmdb://603`, `imdb://tt0133093`, `tvdb://...`.
      - Ældre/legacy-agenter giver kun en enkelt `guid`-streng, fx
        `com.plexapp.agents.imdb://tt0133093?lang=en`.
    Kun at læse `Guid`-listen — som feature #45 gjorde — betyder at hele
    biblioteker på legacy-agenter falder tilbage til titel-matchning uden at
    det er synligt nogen steder. Derfor læses begge, og fejlsøgnings-
    endpointet rapporterer hvor mange elementer der faktisk havde hvad.
    """
    tmdb_id: int | None = None
    imdb_id: str | None = None

    guids = [g.get("id", "") for g in item.get("Guid", []) or []]
    legacy = item.get("guid")
    if isinstance(legacy, str):
        guids.append(legacy)

    for guid in guids:
        if not isinstance(guid, str):
            continue
        tmdb_match = re.search(r"(?:themoviedb|tmdb)://(\d+)", guid)
        if tmdb_match and tmdb_id is None:
            tmdb_id = int(tmdb_match.group(1))
        imdb_match = re.search(r"imdb://(tt\d+)", guid)
        if imdb_match and imdb_id is None:
            imdb_id = imdb_match.group(1)

    return tmdb_id, imdb_id


async def _fetch_server_info(client: httpx.AsyncClient) -> tuple[dict | None, str | None]:
    """Rod-endpointet giver både friendlyName, version og machineIdentifier
    — sidstnævnte skal med i afspilnings-URL'en. Returnerer (info, fejl)."""
    try:
        response = await client.get(_base_url() + "/", headers=_headers(), timeout=IDENTITY_TIMEOUT)
    except httpx.HTTPError as exc:
        return None, f"Kunne ikke nå Plex-serveren: {exc}"

    if response.status_code == 401:
        return None, "Plex afviste token'et (HTTP 401) — er X-Plex-Token korrekt?"
    if response.status_code != 200:
        return None, f"Uventet svar fra Plex (HTTP {response.status_code})"

    try:
        return response.json().get("MediaContainer", {}), None
    except ValueError:
        # En Plex-server der svarer XML i stedet for JSON betyder næsten
        # altid at Accept-headeren blev tabt af en reverse proxy foran den.
        return None, "Plex svarede ikke med JSON — peger URL'en på en Plex-server?"


async def _fetch_sections(client: httpx.AsyncClient) -> tuple[list[dict], str | None]:
    try:
        response = await client.get(f"{_base_url()}/library/sections", headers=_headers())
    except httpx.HTTPError as exc:
        return [], f"Kunne ikke hente Plex-biblioteker: {exc}"

    if response.status_code != 200:
        return [], f"Kunne ikke hente Plex-biblioteker (HTTP {response.status_code})"

    try:
        return response.json().get("MediaContainer", {}).get("Directory", []) or [], None
    except ValueError:
        return [], "Plex' biblioteks-liste kunne ikke læses som JSON"


async def _fetch_section_items(client: httpx.AsyncClient, section_key: str) -> list[dict]:
    """Henter alle elementer i én sektion, sidevist. `includeGuids=1` er det
    der overhovedet får `Guid`-listen med i `/all`-svaret — uden den er der
    ingen TMDb-id'er at matche på, kun titler."""
    items: list[dict] = []
    for page in range(MAX_PAGES):
        headers = {
            **_headers(),
            "X-Plex-Container-Start": str(page * PAGE_SIZE),
            "X-Plex-Container-Size": str(PAGE_SIZE),
        }
        try:
            response = await client.get(
                f"{_base_url()}/library/sections/{section_key}/all",
                headers=headers,
                params={"includeGuids": 1},
            )
        except httpx.HTTPError as exc:
            logger.warning("Plex: sektion %s side %s fejlede: %s", section_key, page, exc)
            break

        if response.status_code != 200:
            logger.warning(
                "Plex: sektion %s side %s gav HTTP %s", section_key, page, response.status_code
            )
            break

        try:
            batch = response.json().get("MediaContainer", {}).get("Metadata", []) or []
        except ValueError:
            logger.warning("Plex: sektion %s side %s var ikke JSON", section_key, page)
            break

        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    else:
        logger.warning(
            "Plex: sektion %s nåede sidegrænsen (%s sider) — der kan mangle elementer",
            section_key,
            MAX_PAGES,
        )

    return items


async def fetch_library() -> PlexFetchResult:
    """Henter hele Plex-bibliotekets film- og serie-index. Kaster aldrig."""
    if not is_configured():
        missing = []
        if not settings.plex_server_url:
            missing.append("server-URL")
        if not settings.plex_token:
            missing.append("token")
        return PlexFetchResult(ok=False, error=f"Plex er ikke konfigureret (mangler {' og '.join(missing)})")

    async with _client() as client:
        info, error = await _fetch_server_info(client)
        if error is not None:
            logger.warning("Plex-forbindelse fejlede: %s", error)
            return PlexFetchResult(ok=False, error=error)

        directories, error = await _fetch_sections(client)
        if error is not None:
            logger.warning("Plex-sektioner kunne ikke hentes: %s", error)
            return PlexFetchResult(
                ok=False,
                error=error,
                server_name=info.get("friendlyName"),
                server_version=info.get("version"),
                machine_identifier=info.get("machineIdentifier"),
            )

        sections: list[PlexSectionResult] = []
        items: list[PlexItem] = []

        for directory in directories:
            section_type = directory.get("type")
            if section_type not in ("movie", "show"):
                continue  # musik, fotos osv. er irrelevante her

            section = PlexSectionResult(
                key=str(directory.get("key")),
                title=directory.get("title", "?"),
                type=section_type,
            )
            for raw in await _fetch_section_items(client, section.key):
                rating_key = raw.get("ratingKey")
                title = raw.get("title")
                if rating_key is None or not title:
                    continue
                tmdb_id, imdb_id = _guid_ids(raw)
                section.item_count += 1
                if tmdb_id is not None:
                    section.with_tmdb_guid += 1
                if imdb_id is not None:
                    section.with_imdb_guid += 1
                items.append(
                    PlexItem(
                        kind=section_type,
                        rating_key=str(rating_key),
                        title=title,
                        year=raw.get("year"),
                        tmdb_id=tmdb_id,
                        imdb_id=imdb_id,
                    )
                )
            sections.append(section)

    logger.info(
        "Plex-bibliotek hentet: %s sektioner, %s elementer (%s med TMDb-id)",
        len(sections),
        len(items),
        sum(section.with_tmdb_guid for section in sections),
    )
    return PlexFetchResult(
        ok=True,
        server_name=info.get("friendlyName"),
        server_version=info.get("version"),
        machine_identifier=info.get("machineIdentifier"),
        sections=sections,
        items=items,
    )


def build_play_url(rating_key: str, machine_identifier: str) -> str:
    return (
        f"{_base_url()}/web/index.html#!/server/{machine_identifier}"
        f"/details?key=%2Flibrary%2Fmetadata%2F{rating_key}"
    )
