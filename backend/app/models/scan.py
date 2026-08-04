from typing import Literal

from pydantic import BaseModel


# Feature #77 — hvilken af de fire stregkode-kilder der faktisk matchede,
# så det kan gemmes på filmen/serien og indgå i Statistik-siden.
BarcodeSource = Literal["upcitemdb", "discogs", "upcdatabase", "ean_search"]


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
    barcode_source: BarcodeSource | None = None
    candidates: list[MovieCandidate]
