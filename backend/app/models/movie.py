from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.models.scan import BarcodeSource


class MovieFormat(str, Enum):
    """Short labels (v0.22.0), digital split into quality tiers. The digital
    tiers themselves were shortened again in v0.84.0 (Digital-HD -> D-HD
    etc.) — see `movie_repository._migrate_format_labels` and
    `tv_show_repository._migrate_format_labels` for the one-time rename of
    existing documents' stored values from the old, longer labels."""

    VHS = "VHS"
    DVD = "DVD"
    BLU_RAY = "BD"
    UHD_4K = "UHD"
    DIGITAL_UHD = "D-UHD"
    DIGITAL_HD = "D-HD"
    DIGITAL_STD = "D-SD"


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
    # Feature #77 — hvilken stregkode-kilde der matchede, hvis oprettelsen
    # kommer fra et rigtigt scan (aldrig sat ved manuel titel-søgning eller
    # direkte tmdb_id-oprettelse) — bruges kun til Statistik-sidens breakdown.
    barcode_source: BarcodeSource | None = None
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
    # Feature #109 — fritekst (Jans valg: et nyt felt, ikke et tag, ikke en
    # fast enum), fx "DA, EN" eller "Fastbrændt DA". Ingen fast værdiliste,
    # så ingen enum og intet autocomplete-opslag som location/owner har.
    subtitles: str | None = None
    is_wishlist: bool = False

    @model_validator(mode="after")
    def require_tmdb_id_or_title(self) -> "MovieCreate":
        if self.tmdb_id is None and not self.title:
            raise ValueError("Enten tmdb_id eller title skal angives")
        return self

    @model_validator(mode="after")
    def require_media_type_and_format_for_library(self) -> "MovieCreate":
        """Feature #92 — en post i biblioteket skal have både medietype og
        format (Jans krav 2026-08-08).

        Det er ikke bare en datakvalitets-regel: medietypen afgør om posten
        overhovedet får et serienummer, og den beslutning kan ikke træffes
        på et tomt felt. Håndhæves i backend frem for kun i UI'et, jf.
        CLAUDE.md regel 16 — en regel der kun findes i frontend er triviel
        at omgå og gælder ikke for andre klienter.

        Ønskelisten er undtaget: man ejer ikke det man ønsker sig endnu, så
        der er hverken en fysisk udgave at beskrive eller et serienummer at
        tildele."""
        if self.is_wishlist:
            return self
        missing = []
        if self.media_type is None:
            missing.append("media_type")
        if self.format is None:
            missing.append("format")
        if missing:
            raise ValueError(
                f"{' og '.join(missing)} skal angives for en film i biblioteket "
                "(kun ønskelisten er undtaget)"
            )
        return self


class MoviePreview(BaseModel):
    """Read-only, fuld TMDb-metadata for en kandidat (feature #79) — bruges
    til at forhåndsvise rediger-boksen ("kladde"-tilstand) uden at oprette
    noget i databasen endnu. Samme felter som `create_movie` selv gemmer."""

    tmdb_id: int
    title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    genres: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    director: str | None = None
    rating: float | None = None
    runtime: int | None = None
    imdb_url: str | None = None
    trailer_url: str | None = None
    collection_id: int | None = None
    collection_name: str | None = None


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
    subtitles: str | None = None
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
    barcode_source: BarcodeSource | None = None
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
    subtitles: str | None = None
    registered_by: str | None = None
    is_wishlist: bool = False
    personal_rating: int | None = None
    personal_note: str | None = None
    watched: bool = False
    watched_at: datetime | None = None
    collection_id: int | None = None
    collection_name: str | None = None
    created_at: datetime
    updated_at: datetime


class MoviePage(BaseModel):
    """Feature #15 — `total` is the full filtered match count (not just
    `len(items)`), so the frontend can render page navigation without a
    second round-trip."""

    items: list[Movie]
    total: int


class CollectionPart(BaseModel):
    tmdb_id: int
    title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    owned: bool
    owned_movie_id: str | None = None
    owned_is_wishlist: bool = False


class CollectionInfo(BaseModel):
    id: int
    name: str | None = None
    poster_url: str | None = None
    parts: list[CollectionPart]


class NamedCount(BaseModel):
    name: str
    count: int


class CollectionStats(BaseModel):
    total_movies: int
    total_runtime_minutes: int
    watched_count: int
    unwatched_count: int
    genre_breakdown: list[NamedCount]
    decade_breakdown: list[NamedCount]
    format_breakdown: list[NamedCount]
    top_directors: list[NamedCount]
    top_actors: list[NamedCount]
    # Feature #77 — kun film/serier tilføjet via et rigtigt stregkode-scan
    # tæller med (se MovieCreate.barcode_source's docstring); dækker film+TV.
    barcode_source_breakdown: list[NamedCount]


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


class SerialHolder(BaseModel):
    """BUGS.md #56 — svar på "hvem holder dette nummer i samme serie?", brugt af
    bibliotekets byt-plads-bekræftelse før et serienummer ændres. `title` er
    None hvis nummeret er frit (så viser UI'et ingen bekræftelse og gemmer
    direkte)."""

    title: str | None = None


class DeletedMovie(BaseModel):
    id: str
    serial_number: int | None = None
    title: str
    year: int | None = None
    format: str | None = None
    deleted_at: datetime
    deleted_by: str | None = None
