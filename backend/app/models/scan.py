from typing import Literal

from pydantic import BaseModel


class ScanLookupRequest(BaseModel):
    barcode: str


class MovieCandidate(BaseModel):
    tmdb_id: int
    title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    rating: float | None = None
    # Defaults to "movie" so the existing media-specific endpoints
    # (/api/movies/tmdb-search, /api/tv-shows/tmdb-search) don't need to
    # pass it explicitly — only /api/scan/lookup's merged results (feature
    # #49) actually vary it per candidate.
    media_kind: Literal["movie", "tv"] = "movie"


class ScanLookupResponse(BaseModel):
    guessed_title: str | None
    candidates: list[MovieCandidate]
