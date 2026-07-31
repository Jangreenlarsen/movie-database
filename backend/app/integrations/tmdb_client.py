import httpx

from app.core.config import settings
from app.core.errors import TmdbNotFoundError, TmdbUnavailableError

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"


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
    return round(vote_average, 1) if vote_average else None


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
    response.raise_for_status()

    results = response.json().get("results", [])
    return [_to_candidate(item) for item in results[:8]]


async def get_movie_details(tmdb_id: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            detail_response = await client.get(
                f"{BASE_URL}/movie/{tmdb_id}", headers=_headers()
            )
            credits_response = await client.get(
                f"{BASE_URL}/movie/{tmdb_id}/credits", headers=_headers()
            )
    except httpx.HTTPError as exc:
        raise TmdbUnavailableError(f"TMDb er ikke tilgængelig: {exc}") from exc

    if detail_response.status_code == 404:
        raise TmdbNotFoundError(tmdb_id)
    if detail_response.status_code == 401:
        raise TmdbUnavailableError("TMDb afviste API-tokenet (401) — tjek TMDB_API_TOKEN")
    detail_response.raise_for_status()
    credits_response.raise_for_status()

    detail = detail_response.json()
    credits = credits_response.json()

    return {
        "tmdb_id": detail["id"],
        "title": detail.get("title"),
        "year": _year_from_release_date(detail.get("release_date")),
        "poster_url": _poster_url(detail.get("poster_path")),
        "overview": detail.get("overview"),
        "genres": [genre["name"] for genre in detail.get("genres", [])],
        "cast": [member["name"] for member in credits.get("cast", [])[:10]],
        "rating": _rating(detail.get("vote_average")),
    }
