from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class MovieFormat(str, Enum):
    VHS = "VHS"
    DVD = "DVD"
    BLU_RAY = "Blu-ray"
    UHD_4K = "4K Ultra HD"
    DIGITAL = "Digital"


class AudioType(str, Enum):
    STEREO = "Stereo"
    MONO = "Mono"
    DOLBY_DIGITAL = "Dolby Digital"
    DOLBY_DIGITAL_5_1 = "Dolby Digital 5.1"
    DOLBY_DIGITAL_7_1 = "Dolby Digital 7.1"
    DTS = "DTS"
    DTS_HD_MASTER_AUDIO = "DTS-HD Master Audio"
    DOLBY_ATMOS = "Dolby Atmos"
    DOLBY_TRUEHD = "Dolby TrueHD"


class MovieCreate(BaseModel):
    """Either `tmdb_id` (metadata is fetched from TMDb server-side) or a
    manual `title` must be given. See ARCHITECTURE.md scan-til-gem flow."""

    tmdb_id: int | None = None
    barcode: str | None = None
    tags: list[str] = Field(default_factory=list)
    format: MovieFormat | None = None
    audio_types: list[AudioType] = Field(default_factory=list)

    title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    runtime: int | None = None
    location: str | None = None
    owner: str | None = None

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
    tags: list[str] | None = None
    format: MovieFormat | None = None
    audio_types: list[AudioType] | None = None
    runtime: int | None = None
    location: str | None = None
    owner: str | None = None
    serial_number: int | None = Field(default=None, gt=0)


class Movie(BaseModel):
    id: str
    serial_number: int
    tmdb_id: int | None = None
    barcode: str | None = None
    title: str
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    format: str | None = None
    audio_types: list[str] = Field(default_factory=list)
    rating: float | None = None
    runtime: int | None = None
    location: str | None = None
    owner: str | None = None
    registered_by: str | None = None
    created_at: datetime
    updated_at: datetime


class DeletedMovie(BaseModel):
    id: str
    serial_number: int | None = None
    title: str
    year: int | None = None
    format: str | None = None
    deleted_at: datetime
    deleted_by: str | None = None
