from pydantic import BaseModel


class ScanLookupRequest(BaseModel):
    barcode: str


class MovieCandidate(BaseModel):
    tmdb_id: int
    title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    rating: float | None = None


class ScanLookupResponse(BaseModel):
    guessed_title: str | None
    candidates: list[MovieCandidate]
