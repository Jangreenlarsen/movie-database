import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.models.announcement import AnnounceMode
from app.models.scan import BarcodeSource

# Feature #123 — undertekster er nu en liste (afkryds Eng/DK + fritekst under
# "Andet") frem for det tidligere frie enkelt-streng-felt (feature #109). De to
# faste valg gemmes præcis som "Eng"/"DK"; alt andet gemmes verbatim som
# fritekst-poster. `SUBTITLE_STANDARD_OPTIONS` er sandheden om hvilke der er de
# faste afkrydsnings-valg (frontend læser dem via attribute-options).
SUBTITLE_STANDARD_OPTIONS = ["Eng", "DK"]

# Kendte skrivemåder → det faste valg. Bruges kun ved migrering af gammel
# fritekst (feature #123); nye poster sender allerede de rene værdier fra UI'et.
_SUBTITLE_TOKEN_MAP = {
    "da": "DK",
    "dk": "DK",
    "dan": "DK",
    "dansk": "DK",
    "danish": "DK",
    "en": "Eng",
    "eng": "Eng",
    "english": "Eng",
    "engelsk": "Eng",
}


def subtitles_from_free_text(raw: str) -> list[str]:
    """Del en gammel fri undertekst-streng ("DA, EN", "Dansk og Engelsk",
    "Fastbrændt DA") op i liste-form. Rene sprog-tokens mappes til de faste
    valg (Eng/DK); alt der ikke er et rent token bevares verbatim som en
    "Andet"-post, så intet indhold går tabt (Jans valg 2026-08-11)."""
    result: list[str] = []
    for part in re.split(r"[,/;]| og | & |\+", raw):
        token = part.strip()
        if not token:
            continue
        value = _SUBTITLE_TOKEN_MAP.get(token.lower(), token)
        if value not in result:
            result.append(value)
    return result


def coerce_subtitles(value) -> list[str]:
    """Læse-side normalisering: None → [], en liste bevares (trimmet), og en
    gammel fri streng (hvis migreringen af en eller anden grund ikke har rørt
    dokumentet endnu) konverteres på stedet, så modellen aldrig fejler på en
    streng hvor den nu forventer en liste."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return subtitles_from_free_text(str(value))


class MovieFormat(str, Enum):
    """Short labels (v0.22.0), digital split into quality tiers. The digital
    tiers were shortened in v0.84.0 (Digital-HD -> D-HD etc.), and renamed in
    v0.105.0 to resolution-based labels (D-HD -> D-1080, D-UHD -> D-4K, new
    D-720). v0.108.0 (Jans ønske 2026-08-12): de fysiske formater fik et "F-"-
    præfiks (DVD -> F-DVD, BD -> F-BD, UHD -> F-UHD), D-SD blev til D-480, og
    VHS blev fjernet (eksisterende VHS-poster migreres til F-DVD). See
    `movie_repository._migrate_format_labels` and
    `tv_show_repository._migrate_format_labels` for the one-time rewrite of
    existing documents' stored values through the whole label history."""

    DVD = "F-DVD"
    BLU_RAY = "F-BD"
    UHD_4K = "F-UHD"
    DIGITAL_UHD = "D-4K"
    DIGITAL_HD = "D-1080"
    DIGITAL_720 = "D-720"
    DIGITAL_STD = "D-480"


class MediaType(str, Enum):
    PHYSICAL = "Fysisk"
    DIGITAL = "Digital"


class OrderStatus(str, Enum):
    """Feature #114 — bestillingsstatus for en ønskeliste-post. Kun de
    *bestilte* tilstande er enum-værdier; "ikke bestilt" repræsenteres som
    fravær (`None`), så feltet følger `location`/`owner`'s valgfri-mønster i
    stedet for at gemme en fjerde "tom" værdi. Genbruges af tv_show.py."""

    LASERDISKEN = "Bestilt ved Laserdisken"
    IMUSIC = "Bestilt ved iMusic"
    OTHER = "Bestilt ved div."


class WishlistStatus(str, Enum):
    """Feature #144 — et ønske tilføjet af en ikke-admin afventer en admins
    godkendelse; admin-tilføjede (og ældre, fra før feltet) ønsker er godkendt
    fra start. Kun relevant for `is_wishlist`-poster. Genbruges af tv_show.py."""

    PENDING = "pending"
    APPROVED = "approved"


class WishlistRejection(BaseModel):
    """Feature #165 — modparten til godkendelse: "afvis ønske". Afvisning
    fjerner ønsket helt (samme sletning som en almindelig sletning) i stedet
    for en tredje wishlist_status-værdi — et afvist ønske skal ikke blive
    stående som en spøgelsespost i ønskelisten, jf. hvordan et afvist
    sæde-hold (feature #133) heller ikke bliver stående. `message` er
    admins valgfrie begrundelse, sendt til ønske-opretteren via den interne
    besked-funktion (feature #100); tom/udeladt giver en generisk besked i
    stedet. Bruges af både `api/movies.py` og `api/tv_shows.py` (importeret
    direkte herfra, ligesom `WishlistStatus`s mønster i tv_show.py)."""

    message: str | None = Field(default=None, max_length=1000)


class AudioType(str, Enum):
    """Short labels (v0.22.0) — less horizontal space on cards/chips. The
    DTS-HD-varianterne blev omdøbt i v0.105.0 (DTS-HD-M -> DTS-HD5.1,
    DTS-HD-MA-7.1 -> DTS-HD7.1) og en ny DTS5.1 tilføjet — Jans ønske
    2026-08-12. See `movie_repository._migrate_audio_type_labels` (og TV-
    seriernes egen kopi) for the one-time rename of existing documents'
    stored values through the whole label history."""

    STEREO = "Stereo"
    MONO = "Mono"
    DOLBY_DIGITAL = "DD"
    DOLBY_DIGITAL_5_1 = "DD5.1"
    DOLBY_DIGITAL_7_1 = "DD7.1"
    DTS = "DTS"
    DTS_5_1 = "DTS5.1"
    DTS_HD_MASTER_AUDIO = "DTS-HD5.1"
    DTS_HD_MA_7_1 = "DTS-HD7.1"
    DTS_X = "DTS:X"
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
    # Feature #109/#123 — undertekster som liste: de faste valg "Eng"/"DK"
    # (afkryds) plus vilkårlig fritekst under "Andet" (fx "Fastbrændt DA",
    # "Norsk"). Ingen enum — "Andet"-posterne er fri tekst. Tom liste = ingen.
    subtitles: list[str] = Field(default_factory=list)
    # Feature #114 — kun relevant for ønskeliste-poster; None = ikke bestilt.
    order_status: OrderStatus | None = None
    is_wishlist: bool = False
    # Feature #222 — transient: styrer kun om en broadcast-besked ("ny titel
    # i samlingen") sendes til alle brugere ved denne oprettelse. Aldrig
    # gemt på selve dokumentet (samme mønster som ScreeningCreate.notify_scope).
    notify_all: bool = False
    # Feature #228 — erstatter `notify_all` som styring (den bevares som
    # alias for "now", se announcement_service.resolve_mode). Transient,
    # aldrig gemt på dokumentet.
    announce: AnnounceMode | None = None

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
    # Feature #123 — None = feltet ikke sendt; [] = ryddet. Samme mønster som
    # audio_types ovenfor.
    subtitles: list[str] | None = None
    order_status: OrderStatus | None = None
    is_wishlist: bool | None = None
    # Feature #222 — samme transiente felt som MovieCreate, men styrer her
    # broadcasten ved "flyt til bibliotek" (ønske → ejet). Poppes ud af
    # `fields` i update_movie, aldrig gemt på dokumentet.
    notify_all: bool = False
    # Feature #228 — erstatter `notify_all` som styring (den bevares som
    # alias for "now", se announcement_service.resolve_mode). Transient,
    # aldrig gemt på dokumentet.
    announce: AnnounceMode | None = None
    # Feature #144 — kun en admin må sætte denne (godkende); håndhæves i
    # service-laget (update_movie).
    wishlist_status: WishlistStatus | None = None
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
    subtitles: list[str] = Field(default_factory=list)
    order_status: str | None = None
    registered_by: str | None = None
    is_wishlist: bool = False
    # Feature #144 — "pending"/"approved" på ønskeliste-poster (None på
    # biblioteks-poster og ældre ønsker uden feltet — de tælles som godkendt).
    wishlist_status: str | None = None
    # Feature #145 — sat ved læsning: True hvis ønskets titel falder sammen med
    # en titel der allerede er i biblioteket (film eller TV). Aldrig gemt.
    name_in_library: bool | None = None
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
    # Feature #201 (Jan: "i 'Del af samlingen:' skal fremgå om ... den er i
    # digital eller fysiske version") — kun meningsfuld når `owned` er sand
    # og delen IKKE er på ønskelisten (en ønske-post har ingen medietype
    # endnu, feature #92). `None` for TMDb-delene der slet ikke er anskaffet.
    owned_media_type: str | None = None


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
    # Feature #159 — nye film+TV-serier tilføjet til biblioteket, én bar pr.
    # af de seneste WEEKLY_ADDITIONS_WEEKS uger (altid det faste antal
    # entries, inkl. uger med 0 — et hul i en tidsserie er misvisende).
    weekly_additions: list[NamedCount]


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
    # BUGS.md — uden medietypen kan frontend ikke vise M/T/D-præfikset, og et
    # dublet-fund ser derfor identisk ud uanset om det er den fysiske disk
    # eller den digitale/Plex-udgave der allerede er registreret.
    media_type: str | None = None


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


class DeletedMoviePage(BaseModel):
    entries: list[DeletedMovie] = Field(default_factory=list)
    total: int
