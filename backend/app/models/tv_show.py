from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.movie import AudioType, MediaType, MovieFormat


class Episode(BaseModel):
    episode_number: int
    name: str | None = None
    air_date: str | None = None
    watched: bool = False
    watched_at: datetime | None = None


class Season(BaseModel):
    season_number: int
    name: str | None = None
    episode_count: int = 0
    air_date: str | None = None
    poster_url: str | None = None
    owned: bool = False
    # Empty until the season is first marked owned — see ARCHITECTURE.md's
    # "Lazy sæson/episode-load" note (feature #48).
    episodes: list[Episode] = Field(default_factory=list)


class TvShowCreate(BaseModel):
    """Either `tmdb_id` (metadata is fetched from TMDb server-side) or a
    manual `name` must be given — same contract as MovieCreate."""

    tmdb_id: int | None = None
    barcode: str | None = None
    tags: list[str] = Field(default_factory=list)
    format: MovieFormat | None = None
    audio_types: list[AudioType] = Field(default_factory=list)
    media_type: MediaType | None = None

    name: str | None = None
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    location: str | None = None
    owner: str | None = None
    is_wishlist: bool = False

    @model_validator(mode="after")
    def require_tmdb_id_or_name(self) -> "TvShowCreate":
        if self.tmdb_id is None and not self.name:
            raise ValueError("Enten tmdb_id eller name skal angives")
        return self


class TvShowUpdate(BaseModel):
    name: str | None = None
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] | None = None
    cast: list[str] | None = None
    tags: list[str] | None = None
    format: MovieFormat | None = None
    audio_types: list[AudioType] | None = None
    media_type: MediaType | None = None
    location: str | None = None
    owner: str | None = None
    is_wishlist: bool | None = None
    serial_number: int | None = Field(default=None, gt=0)
    personal_rating: int | None = Field(default=None, ge=1, le=10)
    personal_note: str | None = None
    watched: bool | None = None
    watched_at: datetime | None = None


class TvShow(BaseModel):
    id: str
    serial_number: int | None = None
    tmdb_id: int | None = None
    barcode: str | None = None
    name: str
    year: int | None = None
    end_year: int | None = None
    status: str | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    creators: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    format: str | None = None
    audio_types: list[str] = Field(default_factory=list)
    media_type: str | None = None
    rating: float | None = None
    number_of_seasons: int | None = None
    number_of_episodes: int | None = None
    imdb_url: str | None = None
    location: str | None = None
    owner: str | None = None
    registered_by: str | None = None
    is_wishlist: bool = False
    personal_rating: int | None = None
    personal_note: str | None = None
    watched: bool = False
    watched_at: datetime | None = None
    seasons: list[Season] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SeasonOwnedUpdate(BaseModel):
    owned: bool


class EpisodeWatchedUpdate(BaseModel):
    watched: bool
    watched_at: datetime | None = None


class DuplicateTvShowMatch(BaseModel):
    id: str
    name: str
    serial_number: int | None = None
    is_wishlist: bool = False


class DeletedTvShow(BaseModel):
    id: str
    serial_number: int | None = None
    name: str
    year: int | None = None
    format: str | None = None
    deleted_at: datetime
    deleted_by: str | None = None
