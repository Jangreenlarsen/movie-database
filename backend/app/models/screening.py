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
    # Feature #85 — begge valgfri og gemt PR. BRUGER, ikke på anmodningen
    # som helhed: flere personer kan ønske samme titel, og deres beskeder/
    # tidspunkter er hver deres. `message` er fri tekst ("gerne en fredag
    # aften"), `preferred_at` et konkret forslag admin kan planlægge ud fra.
    # Defaults gør ældre dokumenter (fra før #85) læsbare uden migration.
    message: str | None = None
    preferred_at: datetime | None = None


class ScreeningRequestCreate(BaseModel):
    media_kind: MediaKind
    movie_id: str | None = None
    tv_show_id: str | None = None
    # Feature #85 — fri tekst, fortsat valgfri.
    message: str | None = Field(default=None, max_length=500)
    # Feature #176 gjorde denne påkrævet for alle; feature #177 (Jan: "vi
    # skal kunne sætte om guest ... skal bruge dato/tid eller ikke") gjorde
    # kravet betinget igen for guest-rollen specifikt — derfor optional her
    # på model-niveau, med selve håndhævelsen flyttet til
    # `screening_service._enforce_preferred_at` (som KENDER den kaldende
    # brugers rolle, hvilket en Pydantic field-validator ikke gør). Standard/
    # admin er fortsat altid påkrævet, uanset indstillingen.
    preferred_at: datetime | None = None

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
    # Feature #162 — se den identiske note ved request_id: en åben
    # afstemning markeres "scheduled" og alle der stemte får besked, i
    # stedet for at afstemningen bare bliver stående uændret for evigt.
    poll_id: str | None = None
    # Feature #170 — Jan: en visning kan sættes som et privat arrangement,
    # så gæst-rollen (feature #72) ikke kan booke sæder på den. Håndhæves i
    # backend (reservation_service.reserve_seats), ikke kun ved at skjule
    # sæde-knappen i UI'et.
    is_private: bool = False

    @model_validator(mode="after")
    def check_reference(self) -> "ScreeningCreate":
        _validate_media_reference(self.media_kind, self.movie_id, self.tv_show_id)
        return self


class ScreeningUpdate(BaseModel):
    scheduled_at: datetime | None = None
    note: str | None = None
    is_private: bool | None = None


class Screening(BaseModel):
    id: str
    media_kind: MediaKind
    movie_id: str | None = None
    tv_show_id: str | None = None
    scheduled_at: datetime
    note: str | None = None
    is_private: bool = False
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
