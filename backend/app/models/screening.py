from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

MediaKind = Literal["movie", "tv"]
ScreeningRequestStatus = Literal["pending", "scheduled", "declined"]


def _validate_media_reference(media_kind: str, movie_id: str | None, tv_show_id: str | None) -> None:
    if media_kind == "movie" and not movie_id:
        raise ValueError("movie_id er påkrævet når media_kind er 'movie'")
    if media_kind == "tv" and not tv_show_id:
        raise ValueError("tv_show_id er påkrævet når media_kind er 'tv'")


class RequestedBy(BaseModel):
    username: str
    requested_at: datetime


class ScreeningRequestCreate(BaseModel):
    media_kind: MediaKind
    movie_id: str | None = None
    tv_show_id: str | None = None

    @model_validator(mode="after")
    def check_reference(self) -> "ScreeningRequestCreate":
        _validate_media_reference(self.media_kind, self.movie_id, self.tv_show_id)
        return self


class ScreeningRequestUpdate(BaseModel):
    # Only "declined" is a direct status edit here — a request becomes
    # "scheduled" only as a side effect of creating a Screening from it
    # (see screening_service.create_screening), never via a direct PATCH.
    status: Literal["declined"]


class ScreeningRequest(BaseModel):
    id: str
    media_kind: MediaKind
    movie_id: str | None = None
    tv_show_id: str | None = None
    status: ScreeningRequestStatus
    requested_by: list[RequestedBy]
    created_at: datetime
    updated_at: datetime
    # Enriched at read-time from the referenced movie/tv_show — never
    # stored on the request document itself (see screening_service).
    title: str | None = None
    year: int | None = None
    poster_url: str | None = None


class ScreeningCreate(BaseModel):
    media_kind: MediaKind
    movie_id: str | None = None
    tv_show_id: str | None = None
    scheduled_at: datetime
    note: str | None = None
    # If set, the referenced pending request is marked "scheduled" as part
    # of the same action instead of being left dangling in the queue.
    request_id: str | None = None

    @model_validator(mode="after")
    def check_reference(self) -> "ScreeningCreate":
        _validate_media_reference(self.media_kind, self.movie_id, self.tv_show_id)
        return self


class ScreeningUpdate(BaseModel):
    scheduled_at: datetime | None = None
    note: str | None = None


class Screening(BaseModel):
    id: str
    media_kind: MediaKind
    movie_id: str | None = None
    tv_show_id: str | None = None
    scheduled_at: datetime
    note: str | None = None
    created_by: str
    created_at: datetime
    # Enriched at read-time from the referenced movie/tv_show (feature
    # #63) — kept live-synced with the library instead of duplicated onto
    # the screening document, so a later TMDb sync/poster change is
    # reflected automatically on the Voldby BIO front page.
    title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    trailer_url: str | None = None
    imdb_url: str | None = None
    genres: list[str] = Field(default_factory=list)
    rating: float | None = None
