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
from collections import Counter
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
    # Feature #91 — Plex' egen `videoResolution` ("4k", "1080", "720", "sd"
    # …). Kun sat for film: en serie har ingen opløsning i sig selv, den
    # ligger på episoderne (se fetch_show_details).
    resolution: str | None = None


@dataclass
class PlexShowDetails:
    """Det der kun kan hentes pr. serie, ikke fra sektions-listen."""

    seasons: list[int]
    resolution: str | None


@dataclass
class PlexClientInfo:
    """Én Plex-klient PMS lige nu kan se på LAN'et (feature #178) — brugt
    udelukkende til admin-opsætningen der finder Shield TV'ets client-id, en
    enkelt gang. Selve afspilnings-kaldet adresserer klienten direkte via det
    gemte id, uden at spørge `/clients` igen."""

    name: str
    machine_identifier: str
    product: str | None = None


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


# Groft kvalitets-rangement, kun brugt til at bryde stemmelighed mellem to
# lige hyppige opløsninger i en serie. Ukendte værdier ender bagerst.
def _resolution_rank(resolution: str) -> int:
    value = resolution.strip().lower()
    if value in ("4k", "2160", "2160p"):
        return 4
    digits = re.match(r"(\d+)", value)
    if digits:
        return 3 if int(digits.group(1)) >= 720 else 2
    return 1 if value == "sd" else 0


def _dominant_resolution(resolutions: list[str]) -> str | None:
    """Den opløsning der bedst repræsenterer en serie (feature #91).

    Den *hyppigste*, ikke den højeste: ét enkelt 4K-afsnit ud af tres gør
    ikke serien til en UHD-udgave. Står to opløsninger lige, vinder den
    højere kvalitet."""
    if not resolutions:
        return None
    counts = Counter(resolutions)
    return max(counts, key=lambda value: (counts[value], _resolution_rank(value)))


def _resolution(item: dict) -> str | None:
    """Plex' `videoResolution` for et element (feature #91).

    Ligger på `Media[]` — den liste over fysiske filer der hører til
    elementet. Har man flere udgaver af samme film liggende (fx en 1080p og
    en 4K), er der flere `Media`-poster; den første er Plex' egen foretrukne.
    """
    for media in item.get("Media") or []:
        value = media.get("videoResolution")
        if value:
            return str(value)
    return None


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


async def _fetch_section_items(
    client: httpx.AsyncClient, section_key: str
) -> tuple[list[dict], str | None]:
    """Henter alle elementer i én sektion, sidevist. `includeGuids=1` er det
    der overhovedet får `Guid`-listen med i `/all`-svaret — uden den er der
    ingen TMDb-id'er at matche på, kun titler.

    Returnerer (elementer, fejl). BUGS.md #51: en fejl undervejs afbrød før
    løkken og returnerede den *delvise* liste som om den var hele sektionen.
    Et halvt hentet bibliotek er værre end intet: filmene der manglede blev
    rapporteret som "ikke fundet i Plex", selvom de lå der — og i værste fald
    (fejl på første side) så hele biblioteket tomt ud, uden at noget sted
    fortalte hvorfor. Enhver ufuldstændig hentning er derfor nu en fejl."""
    items: list[dict] = []
    total_size = None
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
            return items, f"sektion {section_key} side {page} fejlede: {exc}"

        if response.status_code != 200:
            return items, f"sektion {section_key} side {page} gav HTTP {response.status_code}"

        try:
            container = response.json().get("MediaContainer", {})
        except ValueError:
            return items, f"sektion {section_key} side {page} var ikke JSON"

        batch = container.get("Metadata", []) or []
        # Plex oplyser sektionens fulde størrelse på hver side; den bruges
        # nedenfor til at fange en afkortet hentning der ellers ville se
        # fuldstændig ud.
        if total_size is None and isinstance(container.get("totalSize"), int):
            total_size = container["totalSize"]

        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    else:
        return items, f"sektion {section_key} nåede sidegrænsen ({MAX_PAGES} sider)"

    if total_size is not None and len(items) != total_size:
        return items, (
            f"sektion {section_key} gav {len(items)} elementer, men Plex oplyser {total_size}"
        )

    return items, None


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
            raw_items, section_error = await _fetch_section_items(client, section.key)
            if section_error is not None:
                logger.warning("Plex-hentning ufuldstændig: %s", section_error)
                return PlexFetchResult(
                    ok=False,
                    error=(
                        f"Plex-biblioteket kunne ikke hentes fuldstændigt ({section_error}). "
                        "Et delvist hentet bibliotek ville få film der ligger i Plex til at "
                        "se ud som om de ikke gjorde — prøv igen."
                    ),
                    server_name=info.get("friendlyName"),
                    server_version=info.get("version"),
                    machine_identifier=info.get("machineIdentifier"),
                )
            for raw in raw_items:
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
                        resolution=_resolution(raw),
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


async def fetch_show_details(rating_key: str) -> PlexShowDetails:
    """Sæsoner og opløsning for én serie — det `/all` ikke kan svare på.

    Feature #90 spurgte oprindeligt `/children`, som lister seriens sæsoner
    direkte. Feature #91 skal også bruge opløsningen, og den findes kun på
    episoderne. `/allLeaves` returnerer alle seriens episoder i ét kald, hver
    med `parentIndex` (sæsonnummeret) og sin egen `Media` — så begge svar
    kommer nu ud af det samme ene kald, i stedet for at skulle bruge to.

    En sæson der ikke har nogen episoder liggende, optræder heller ikke her —
    hvilket er præcis det rigtige svar på "hvilke sæsoner har jeg?".

    Sæson 0 (Plex' "Specials") springes over: den svarer til TMDb's
    special-sæson, som appens egen sæson-model heller ikke regner med.

    Enhver fejl giver tomme sæsoner og ingen opløsning — en serie uden dem
    er stadig værd at importere."""
    empty = PlexShowDetails(seasons=[], resolution=None)
    if not is_configured():
        return empty

    try:
        async with _client() as client:
            response = await client.get(
                f"{_base_url()}/library/metadata/{rating_key}/allLeaves", headers=_headers()
            )
    except httpx.HTTPError as exc:
        logger.warning("Plex: episoder for %s kunne ikke hentes: %s", rating_key, exc)
        return empty

    if response.status_code != 200:
        logger.warning("Plex: episoder for %s gav HTTP %s", rating_key, response.status_code)
        return empty

    try:
        episodes = response.json().get("MediaContainer", {}).get("Metadata", []) or []
    except ValueError:
        logger.warning("Plex: episode-svar for %s var ikke JSON", rating_key)
        return empty

    seasons = set()
    resolutions: list[str] = []
    for episode in episodes:
        season_number = episode.get("parentIndex")
        if isinstance(season_number, int) and season_number > 0:
            seasons.add(season_number)
        resolution = _resolution(episode)
        if resolution:
            resolutions.append(resolution)

    return PlexShowDetails(seasons=sorted(seasons), resolution=_dominant_resolution(resolutions))


def build_play_url(rating_key: str, machine_identifier: str) -> str:
    return (
        f"{_base_url()}/web/index.html#!/server/{machine_identifier}"
        f"/details?key=%2Flibrary%2Fmetadata%2F{rating_key}"
    )


async def fetch_clients() -> tuple[list[PlexClientInfo], int, str | None]:
    """`GET /clients` — Plex-klienter PMS lige nu kan se annonceret på
    LAN'et (samme liste Plex Web selv bruger til "Afspil på andet apparat").
    Kun til admin-opsætningen (feature #178): Shield TV'et skal selv have
    Plex-appen åben/logget ind i det øjeblik dette kaldes, ellers optræder
    den slet ikke — bruges derfor kun til at *finde* dens client-id én gang,
    ikke ved hver afspilning.

    BUGS.md #76 (Jan: "der skal nok noget feedback til så man kan se at din
    code gør det korekte") — logger nu både forespørgslen og hele PMS'
    rå svar (regel 11), og returnerer *også* det samlede antal entries PMS
    rapporterede, `raw_count`, uafhængigt af hvor mange der faktisk havde et
    brugbart `machineIdentifier`. Uden det tal kan et tomt resultat aldrig
    skelnes fra "PMS svarede korrekt og rapporterer reelt nul registrerede
    klienter" (en Plex-/netværks-begrænsning, fx GDM/AP-isolation) versus "vi
    fik et svar med indhold, men filtrerede det forkert" (en fejl i denne
    funktion) — begge så identiske ud for brugeren før denne ændring."""
    url = f"{_base_url()}/clients"
    if not is_configured():
        return [], 0, "Plex er ikke konfigureret."

    logger.info("Plex: henter klientliste (%s)", url)

    try:
        async with _client() as client:
            response = await client.get(url, headers=_headers())
    except httpx.HTTPError as exc:
        logger.warning("Plex: /clients kunne ikke nås: %s", exc)
        return [], 0, f"Kunne ikke hente Plex-klienter: {exc}"

    if response.status_code != 200:
        logger.warning("Plex: /clients gav HTTP %s", response.status_code)
        return [], 0, f"Uventet svar fra Plex (HTTP {response.status_code})"

    try:
        raw = response.json().get("MediaContainer", {}).get("Server", []) or []
    except ValueError:
        logger.warning("Plex: /clients svarede ikke med JSON")
        return [], 0, "Plex svarede ikke med JSON"

    clients = [
        PlexClientInfo(
            name=entry.get("name") or "?",
            machine_identifier=entry["machineIdentifier"],
            product=entry.get("product"),
        )
        for entry in raw
        if entry.get("machineIdentifier")
    ]
    logger.info(
        "Plex: /clients svarede med %d entries i alt (%d med et brugbart client-id): %s",
        len(raw),
        len(clients),
        [entry.get("name") for entry in raw],
    )
    return clients, len(raw), None


async def play_on_client(
    rating_key: str, server_machine_identifier: str, client_identifier: str
) -> tuple[bool, str]:
    """Sender en "afspil nu"-kommando til én bestemt, tidligere fundet Plex-
    klient (feature #178, Jan: "starte den i plex på shield der også") — via
    PMS' egen Companion-relæ, samme mekanisme Plex Web/mobil-appens "Afspil
    på andet apparat" selv bruger. **Forudsætning, ikke rettet af os**: Plex-
    appen skal allerede køre og være logget ind på klienten — Plex kan ikke
    selv tænde eller starte appen fra slukket/standby, kun sende en kommando
    til en app der allerede lytter.

    Jan, opfølgning 2026-08-18: afspilning startet herfra transcodede video
    ned til HD og transcodede lyd, hvor direkte afspilning på Shielden ikke
    gør det. `directPlay=1`/`directStream=1` (udokumenteret, men bredt brugt
    Companion-parameter i tredjeparts Plex-automatisering, fx Home Assistant-
    integrationer) beder PMS forsøge direkte afspilning fremfor at
    transcode — men er **ikke en garanti**: er kilden reelt inkompatibel med
    klientens erklærede evner (container/codec/bitrate, eller en lydkodning
    klienten/receiveren ikke kan passe igennem), transcoder PMS stadig,
    uanset denne parameter."""
    if not is_configured():
        return False, "Plex er ikke konfigureret."

    parsed = httpx.URL(_base_url())
    default_port = 443 if parsed.scheme == "https" else 32400
    params = {
        "key": f"/library/metadata/{rating_key}",
        "offset": "0",
        "machineIdentifier": server_machine_identifier,
        "protocol": parsed.scheme,
        "address": parsed.host,
        "port": str(parsed.port or default_port),
        "token": settings.plex_token,
        "type": "video",
        "directPlay": "1",
        "directStream": "1",
    }
    headers = {**_headers(), "X-Plex-Target-Client-Identifier": client_identifier}

    logger.info(
        "Plex: sender playMedia (rating_key=%s) til klient %s", rating_key, client_identifier
    )

    try:
        async with _client() as client:
            response = await client.get(
                f"{_base_url()}/player/playback/playMedia", params=params, headers=headers
            )
    except httpx.HTTPError as exc:
        logger.warning("Plex: playMedia til %s kunne ikke nås: %s", client_identifier, exc)
        return False, f"Kunne ikke nå Plex-serveren: {exc}"

    if response.status_code == 401:
        logger.warning("Plex: playMedia afvist (HTTP 401)")
        return False, "Plex afviste token'et (HTTP 401)."
    if response.status_code == 404:
        logger.warning("Plex: playMedia til %s gav HTTP 404 (klienten ikke fundet af PMS)", client_identifier)
        return False, "Shield TV'et svarede ikke — er Plex-appen åben og tændt på den?"
    if response.status_code >= 400:
        logger.warning("Plex: playMedia til %s gav HTTP %s", client_identifier, response.status_code)
        return False, f"Plex afviste kommandoen (HTTP {response.status_code})."

    logger.info("Plex: playMedia til %s lykkedes (HTTP %s)", client_identifier, response.status_code)
    return True, "Afspilning startet på Shield TV."


async def stop_client(client_identifier: str) -> tuple[bool, str]:
    """Sender en "stop"-kommando til én bestemt, tidligere fundet Plex-
    klient — samme Companion-relæ som `play_on_client`, men uden nogen
    medie-reference: stopper hvad end klienten lige nu afspiller, uafhængigt
    af hvilken film/serie der oprindeligt startede den. Jan, opfølgning
    2026-08-18: "Afspil på Shield TV"-knappen skal være en rigtig
    start/stop-toggle, ikke kun starte."""
    if not is_configured():
        return False, "Plex er ikke konfigureret."

    headers = {**_headers(), "X-Plex-Target-Client-Identifier": client_identifier}

    logger.info("Plex: sender playback/stop til klient %s", client_identifier)

    try:
        async with _client() as client:
            response = await client.get(
                f"{_base_url()}/player/playback/stop",
                params={"type": "video"},
                headers=headers,
            )
    except httpx.HTTPError as exc:
        logger.warning("Plex: stop til %s kunne ikke nås: %s", client_identifier, exc)
        return False, f"Kunne ikke nå Plex-serveren: {exc}"

    if response.status_code == 401:
        logger.warning("Plex: stop afvist (HTTP 401)")
        return False, "Plex afviste token'et (HTTP 401)."
    if response.status_code == 404:
        logger.warning("Plex: stop til %s gav HTTP 404 (klienten ikke fundet af PMS)", client_identifier)
        return False, "Shield TV'et svarede ikke — er Plex-appen stadig åben på den?"
    if response.status_code >= 400:
        logger.warning("Plex: stop til %s gav HTTP %s", client_identifier, response.status_code)
        return False, f"Plex afviste stop-kommandoen (HTTP {response.status_code})."

    logger.info("Plex: stop til %s lykkedes (HTTP %s)", client_identifier, response.status_code)
    return True, "Afspilning stoppet på Shield TV."
