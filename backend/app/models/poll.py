from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.screening import MediaKind, _validate_media_reference

PollStatus = Literal["open", "closed", "scheduled"]


class PollCandidateCreate(BaseModel):
    media_kind: MediaKind
    movie_id: str | None = None
    tv_show_id: str | None = None

    @model_validator(mode="after")
    def check_reference(self) -> "PollCandidateCreate":
        _validate_media_reference(self.media_kind, self.movie_id, self.tv_show_id)
        return self


class PollCreate(BaseModel):
    # Valgfri — en admin behøver ikke navngive hver afstemning ("Fredag
    # aften?" er implicit af selve konteksten den bruges i).
    title: str | None = Field(default=None, max_length=200)
    # Feature #208 (Jan: "afstemming skal kunne sættes en dato på til de
    # film vi stemmer om til forvisning") — hvilken AFTEN der stemmes om,
    # ikke et klokkeslæt (det fastlægges først når vinderen rent faktisk
    # planlægges, se poll_service.create_poll/SchedulePollWinnerForm i
    # frontend, som foreslår denne dato videre til selve
    # visnings-planlægningen). `datetime`, ikke `date` — samme "kun dato
    # betyder navnet, typen er datetime" konvention som Movie/TvShow's
    # `watched_at` allerede bruger (MongoDB/BSON har ingen ren dato-type).
    # Valgfri, som title.
    target_date: datetime | None = None
    candidates: list[PollCandidateCreate]

    @model_validator(mode="after")
    def check_candidates(self) -> "PollCreate":
        if len(self.candidates) < 2:
            raise ValueError("En afstemning kræver mindst 2 kandidater")
        keys = [(c.media_kind, c.movie_id, c.tv_show_id) for c in self.candidates]
        if len(keys) != len(set(keys)):
            raise ValueError("Samme titel kan ikke være kandidat to gange i samme afstemning")
        return self


class PollVoteRequest(BaseModel):
    candidate_index: int = Field(ge=0)


class PollCandidateResult(BaseModel):
    media_kind: MediaKind
    movie_id: str | None = None
    tv_show_id: str | None = None
    # Enriched at read-time fra det refererede bibliotekselement — samme
    # "aldrig gemt på selve dokumentet" mønster som Screening/ScreeningRequest
    # (screening_service._resolve_display_info). `None` hvis titlen siden er
    # slettet fra biblioteket — vises som "Ukendt" i UI'et, ingen særlig
    # oprydning nødvendig (afstemninger er kortlivede af natur).
    title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    vote_count: int = 0


class Poll(BaseModel):
    id: str
    title: str | None = None
    target_date: datetime | None = None
    status: PollStatus
    candidates: list[PollCandidateResult]
    total_votes: int
    # Hvilken kandidat-index DENNE bruger selv har stemt på, eller None —
    # aldrig andre brugeres individuelle stemmer (kun det aggregerede
    # `vote_count` pr. kandidat, feature #162's "synlige undervejs"-valg).
    my_vote: int | None = None
    # Beregnet ved hvert opslag (ikke gemt) — altid korrekt uden en separat
    # skrivning der kunne komme ud af trit med de faktiske stemmer. Tom liste
    # mens afstemningen stadig er åben (kun meningsfuld når lukket/planlagt).
    winner_indices: list[int] = Field(default_factory=list)
    scheduled_screening_id: str | None = None
    created_by: str
    created_at: datetime
    closed_at: datetime | None = None
