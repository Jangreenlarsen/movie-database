from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class MovieFormat(str, Enum):
    """Short labels (v0.22.0), digital split into quality tiers — see
    `movie_repository._migrate_format_labels` for the one-time rename of
    existing documents' stored values from the old, longer labels."""

    VHS = "VHS"
    DVD = "DVD"
    BLU_RAY = "BD"
    UHD_4K = "UHD"
    DIGITAL_UHD = "Digital-UHD"
    DIGITAL_HD = "Digital-HD"
    DIGITAL_STD = "Digital-STD"


class MediaType(str, Enum):
    PHYSICAL = "Fysisk"
    DIGITAL = "Digital"


class AudioType(str, Enum):
    """Short labels (v0.22.0) — less horizontal space on cards/chips. See
    `movie_repository._migrate_audio_type_labels` for the one-time rename of
    existing documents' stored values from the old, longer labels."""

    STEREO = "Stereo"
    MONO = "Mono"
    DOLBY_DIGITAL = "DD"
    DOLBY_DIGITAL_5_1 = "DD5.1"
    DOLBY_DIGITAL_7_1 = "DD7.1"
    DTS = "DTS"
    DTS_HD_MASTER_AUDIO = "DTS-HD-M"
    DOLBY_ATMOS = "Atmos"
    DOLBY_TRUEHD = "D-true-HD"


class MovieCreate(BaseModel):
    """Either `tmdb_id` (metadata is fetched from TMDb server-side) or a
    manual `title` must be given. See ARCHITECTURE.md scan-til-gem flow."""

    tmdb_id: int | None = None
    barcode: str | None = None
    tags: list[str] = Field(default_factory=list)
    format: MovieFormat | None = None
    audio_types: list[AudioType] = Field(default_factory=list)
    media_type: MediaType | None = None

    title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    director: str | None = None
    runtime: int | None = None
    imdb_url: str | None = None
    trailer_url: str | None = None
    location: str | None = None
    owner: str | None = None
    is_wishlist: bool = False

    @model_validator(mode="after")
    def require_tmdb_id_or_title(self) -> "MovieCreate":
        if self.tmdb_id is None and not self.title:
            raise ValueError("Enten tmdb_id eller title skal angives")
        return self


class MovieUpdate(BaseModel):
    title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] | None = None
    cast: list[str] | None = None
    director: str | None = None
    tags: list[str] | None = None
    format: MovieFormat | None = None
    audio_types: list[AudioType] | None = None
    media_type: MediaType | None = None
    runtime: int | None = None
    imdb_url: str | None = None
    trailer_url: str | None = None
    location: str | None = None
    owner: str | None = None
    is_wishlist: bool | None = None
    serial_number: int | None = Field(default=None, gt=0)
    personal_rating: int | None = Field(default=None, ge=1, le=10)
    personal_note: str | None = None
    watched: bool | None = None
    watched_at: datetime | None = None


class Movie(BaseModel):
    id: str
    serial_number: int | None = None
    tmdb_id: int | None = None
    barcode: str | None = None
    title: str
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    director: str | None = None
    tags: list[str] = Field(default_factory=list)
    format: str | None = None
    audio_types: list[str] = Field(default_factory=list)
    media_type: str | None = None
    rating: float | None = None
    runtime: int | None = None
    imdb_url: str | None = None
    trailer_url: str | None = None
    location: str | None = None
    owner: str | None = None
    registered_by: str | None = None
    is_wishlist: bool = False
    personal_rating: int | None = None
    personal_note: str | None = None
    watched: bool = False
    watched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TmdbSyncResult(BaseModel):
    total: int
    synced: int
    failed: int
    failed_titles: list[str] = Field(default_factory=list)
    stopped_early: bool = False


class DuplicateMatch(BaseModel):
    id: str
    title: str
    serial_number: int | None = None
    is_wishlist: bool = False


class DeletedMovie(BaseModel):
    id: str
    serial_number: int | None = None
    title: str
    year: int | None = None
    format: str | None = None
    deleted_at: datetime
    deleted_by: str | None = None
