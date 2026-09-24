import httpx

from app.core.config import settings
from app.core.errors import TmdbNotFoundError, TmdbRateLimitedError, TmdbUnavailableError
from app.integrations.http_json import json_object

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_HOST = "https://image.tmdb.org/t/p"
IMAGE_BASE_URL = f"{IMAGE_HOST}/w500"


def _require_token() -> str:
    if not settings.tmdb_api_token:
        raise TmdbUnavailableError(
            "TMDB_API_TOKEN er ikke konfigureret — se MOVIE_API_REFERENCE.md"
        )
    return settings.tmdb_api_token


def _headers() -> dict:
    return {"Authorization": f"Bearer {_require_token()}", "Accept": "application/json"}


def _year_from_release_date(release_date: str | None) -> int | None:
    if release_date and release_date[:4].isdigit():
        return int(release_date[:4])
    return None


def _poster_url(poster_path: str | None) -> str | None:
    return f"{IMAGE_BASE_URL}{poster_path}" if poster_path else None


def _rating(vote_average: float | None) -> float | None:
    return round(vote_average, 1) if vote_average is not None else None


def _imdb_url(imdb_id: str | None) -> str | None:
    return f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None


def _director(crew: list[dict]) -> str | None:
    for member in crew:
        if member.get("job") == "Director":
            return member.get("name")
    return None


def _trailer_url(videos: list[dict]) -> str | None:
    """First official YouTube trailer, if any — TMDb lists teasers/clips/
    featurettes in the same `videos.results` array, so both site and type
    are checked, not just the first entry. A video entry missing its `key`
    is skipped rather than turned into a broken "...watch?v=None" URL."""
    for video in videos:
        key = video.get("key")
        if key and video.get("site") == "YouTube" and video.get("type") == "Trailer":
            return f"https://www.youtube.com/watch?v={key}"
    return None


def _json(response: httpx.Response) -> dict:
    """BUGS.md #105 — TMDbs svar som et JSON-objekt, ellers en pæn
    TmdbUnavailableError (502) i stedet for en rå JSONDecodeError (500) —
    fx når en proxy eller captive portal svarer 200 med en HTML-side."""
    data = json_object(response)
    if data is None:
        raise TmdbUnavailableError("TMDb svarede med et ugyldigt svar (ikke JSON)")
    return data


def _raise_for_status(response: httpx.Response) -> None:
    """Any TMDb status we don't explicitly translate elsewhere still ends up
    as a clean TmdbUnavailableError (502) instead of an unhandled 500."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise TmdbUnavailableError(
            f"TMDb svarede med uventet status {response.status_code}"
        ) from exc


async def fetch_poster_image(size: str, path: str) -> tuple[bytes, str] | None:
    """Feature #153 — henter de rå billed-bytes for en poster direkte fra
    TMDb's *billed*-CDN (image.tmdb.org), ikke JSON-API'et — intet
    API-token nødvendigt her, TMDb's billeder er offentlige. Bruges
    udelukkende af `poster_cache_service` til at varme cachen op første (og
    eneste) gang et givent (size, path)-par efterspørges. Returnerer None
    ved enhver fejl (netværk, 404 osv.) — kaldestedet cacher da intet og
    lader frontend falde tilbage til sin egen "intet billede"-visning,
    fremfor at kaste en fejl der vælter hele sidevisningen."""
    url = f"{IMAGE_HOST}/{size}/{path}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    return response.content, response.headers.get("content-type", "image/jpeg")


async def test_connection() -> tuple[bool, str]:
    """Feature #75 — TMDb's own /authentication endpoint is the canonical
    way to validate a v3 read-access token."""
    if not settings.tmdb_api_token:
        return False, "Ingen TMDb-nøgle sat"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{BASE_URL}/authentication", headers=_headers())
    except httpx.HTTPError as exc:
        return False, f"Netværksfejl: {exc}"

    if response.status_code == 200:
        return True, "Virker"
    if response.status_code == 401:
        return False, "TMDb afviste nøglen (ugyldig)"
    return False, f"Uventet svar (HTTP {response.status_code})"


def _to_candidate(item: dict) -> dict:
    return {
        "tmdb_id": item["id"],
        "title": item.get("title"),
        "year": _year_from_release_date(item.get("release_date")),
        "poster_url": _poster_url(item.get("poster_path")),
        "rating": _rating(item.get("vote_average")),
    }


async def search_movies(query: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{BASE_URL}/search/movie", headers=_headers(), params={"query": query}
            )
    except httpx.HTTPError as exc:
        raise TmdbUnavailableError(f"TMDb er ikke tilgængelig: {exc}") from exc

    if response.status_code == 401:
        raise TmdbUnavailableError("TMDb afviste API-tokenet (401) — tjek TMDB_API_TOKEN")
    if response.status_code == 429:
        raise TmdbUnavailableError("TMDb rate-limit ramt (429), prøv igen om lidt")
    _raise_for_status(response)

    results = _json(response).get("results", [])
    return [_to_candidate(item) for item in results[:8]]


async def get_movie_details(tmdb_id: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            detail_response = await client.get(
                f"{BASE_URL}/movie/{tmdb_id}",
                headers=_headers(),
                params={"append_to_response": "credits,videos,external_ids"},
            )
    except httpx.HTTPError as exc:
        raise TmdbUnavailableError(f"TMDb er ikke tilgængelig: {exc}") from exc

    if detail_response.status_code == 404:
        raise TmdbNotFoundError(tmdb_id)
    if detail_response.status_code == 401:
        raise TmdbUnavailableError("TMDb afviste API-tokenet (401) — tjek TMDB_API_TOKEN")
    if detail_response.status_code == 429:
        raise TmdbRateLimitedError()
    _raise_for_status(detail_response)

    detail = _json(detail_response)
    credits = detail.get("credits", {})
    videos = detail.get("videos", {}).get("results", [])
    external_ids = detail.get("external_ids", {})
    collection = detail.get("belongs_to_collection")

    return {
        "tmdb_id": detail["id"],
        "title": detail.get("title"),
        "year": _year_from_release_date(detail.get("release_date")),
        "poster_url": _poster_url(detail.get("poster_path")),
        "overview": detail.get("overview"),
        "genres": [genre["name"] for genre in detail.get("genres", [])],
        "cast": [member["name"] for member in credits.get("cast", [])[:10]],
        "director": _director(credits.get("crew", [])),
        "rating": _rating(detail.get("vote_average")),
        "runtime": detail.get("runtime"),
        "imdb_id": external_ids.get("imdb_id"),
        "imdb_url": _imdb_url(external_ids.get("imdb_id")),
        "trailer_url": _trailer_url(videos),
        "collection_id": collection["id"] if collection else None,
        "collection_name": collection["name"] if collection else None,
    }


def _to_tv_candidate(item: dict) -> dict:
    # Mapped to the same shape as _to_candidate (title/year/poster_url/rating)
    # so the frontend can reuse one candidate-picker component for both
    # movie and TV search results (feature #49) — `name` -> `title` is a
    # deliberate boundary translation, not a claim that TV shows have a
    # "title" field internally (the stored TvShow model uses `name`).
    return {
        "tmdb_id": item["id"],
        "title": item.get("name"),
        "year": _year_from_release_date(item.get("first_air_date")),
        "poster_url": _poster_url(item.get("poster_path")),
        "rating": _rating(item.get("vote_average")),
    }


async def search_tv(query: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{BASE_URL}/search/tv", headers=_headers(), params={"query": query}
            )
    except httpx.HTTPError as exc:
        raise TmdbUnavailableError(f"TMDb er ikke tilgængelig: {exc}") from exc

    if response.status_code == 401:
        raise TmdbUnavailableError("TMDb afviste API-tokenet (401) — tjek TMDB_API_TOKEN")
    if response.status_code == 429:
        raise TmdbUnavailableError("TMDb rate-limit ramt (429), prøv igen om lidt")
    _raise_for_status(response)

    results = _json(response).get("results", [])
    return [_to_tv_candidate(item) for item in results[:8]]


async def get_tv_show_details(tv_id: int) -> dict:
    """Series-level metadata plus a *light* season list (number/name/episode
    count/air date/poster, straight from /tv/{id}'s own seasons[]) — no
    per-episode data. See ARCHITECTURE.md's "Lazy sæson/episode-load" note:
    fetching every season's full episode list here would be one extra TMDb
    call per season, wasted for seasons the user doesn't own."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            detail_response = await client.get(
                f"{BASE_URL}/tv/{tv_id}",
                headers=_headers(),
                params={"append_to_response": "credits,external_ids"},
            )
    except httpx.HTTPError as exc:
        raise TmdbUnavailableError(f"TMDb er ikke tilgængelig: {exc}") from exc

    if detail_response.status_code == 404:
        raise TmdbNotFoundError(tv_id)
    if detail_response.status_code == 401:
        raise TmdbUnavailableError("TMDb afviste API-tokenet (401) — tjek TMDB_API_TOKEN")
    if detail_response.status_code == 429:
        raise TmdbRateLimitedError()
    _raise_for_status(detail_response)

    detail = _json(detail_response)
    credits = detail.get("credits", {})
    external_ids = detail.get("external_ids", {})

    return {
        "tmdb_id": detail["id"],
        "name": detail.get("name"),
        "year": _year_from_release_date(detail.get("first_air_date")),
        "end_year": _year_from_release_date(detail.get("last_air_date")),
        "status": detail.get("status"),
        "poster_url": _poster_url(detail.get("poster_path")),
        "overview": detail.get("overview"),
        "genres": [genre["name"] for genre in detail.get("genres", [])],
        "cast": [member["name"] for member in credits.get("cast", [])[:10]],
        "creators": [creator["name"] for creator in detail.get("created_by", [])],
        "rating": _rating(detail.get("vote_average")),
        "number_of_seasons": detail.get("number_of_seasons"),
        "number_of_episodes": detail.get("number_of_episodes"),
        "imdb_id": external_ids.get("imdb_id"),
        "imdb_url": _imdb_url(external_ids.get("imdb_id")),
        "seasons": [
            {
                "season_number": season["season_number"],
                "name": season.get("name"),
                "episode_count": season.get("episode_count") or 0,
                "air_date": season.get("air_date"),
                "poster_url": _poster_url(season.get("poster_path")),
            }
            for season in detail.get("seasons", [])
        ],
    }


async def get_season_details(tv_id: int, season_number: int) -> list[dict]:
    """Full episode list for one season of one show — fetched lazily, only
    when that season is first marked as owned (feature #48)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{BASE_URL}/tv/{tv_id}/season/{season_number}", headers=_headers()
            )
    except httpx.HTTPError as exc:
        raise TmdbUnavailableError(f"TMDb er ikke tilgængelig: {exc}") from exc

    if response.status_code == 404:
        raise TmdbNotFoundError(tv_id)
    if response.status_code == 401:
        raise TmdbUnavailableError("TMDb afviste API-tokenet (401) — tjek TMDB_API_TOKEN")
    if response.status_code == 429:
        raise TmdbRateLimitedError()
    _raise_for_status(response)

    data = _json(response)
    return [
        {
            "episode_number": episode["episode_number"],
            "name": episode.get("name"),
            "air_date": episode.get("air_date"),
        }
        for episode in data.get("episodes", [])
    ]


async def get_collection(collection_id: int) -> dict:
    """Full list of a TMDb "collection" (franchise/box-set)'s films — used to
    show "you own N of M" (FEATURES.md #42). Distinct from get_movie_details:
    this is keyed by TMDb's own collection id, not a movie id."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{BASE_URL}/collection/{collection_id}", headers=_headers()
            )
    except httpx.HTTPError as exc:
        raise TmdbUnavailableError(f"TMDb er ikke tilgængelig: {exc}") from exc

    if response.status_code == 401:
        raise TmdbUnavailableError("TMDb afviste API-tokenet (401) — tjek TMDB_API_TOKEN")
    if response.status_code == 429:
        raise TmdbRateLimitedError()
    _raise_for_status(response)

    data = _json(response)
    return {
        "id": data["id"],
        "name": data.get("name"),
        "poster_url": _poster_url(data.get("poster_path")),
        "parts": [
            {
                "tmdb_id": part["id"],
                "title": part.get("title"),
                "year": _year_from_release_date(part.get("release_date")),
                "poster_url": _poster_url(part.get("poster_path")),
            }
            for part in data.get("parts", [])
        ],
    }
