from typing import Literal

from pydantic import BaseModel, Field

# Hvilken af de to biblioteks-ressourcer et Plex-opslag gælder. Bevidst det
# samme skel som resten af appen (film og TV-serier er adskilte ressourcer,
# se CLAUDE.md) — "show" er Plex' eget navn for en TV-serie-sektion.
PlexKind = Literal["movie", "show"]


class PlexAvailability(BaseModel):
    """Ét biblioteks-elements Plex-status. `matched_by` fortæller *hvordan*
    match'et blev fundet — den er det vigtigste enkelt-felt i fejlsøgningen,
    fordi et titel-baseret match er langt mere usikkert end et tmdb-id-match
    og derfor er den mest sandsynlige kilde til et falsk positivt badge."""

    available: bool
    play_url: str | None = None
    matched_by: Literal["tmdb", "title_year", "title"] | None = None
    plex_title: str | None = None
    plex_year: int | None = None


class PlexAvailabilityMap(BaseModel):
    """Svaret på ét kald pr. fane: hele bibliotekets Plex-status på én gang.
    Frontend slår op i `items` pr. film-/serie-id i stedet for at lave et
    kald pr. kort (feature #88 — den gamle "Tjek Plex"-knap lavede ét kald
    pr. film, manuelt udløst)."""

    configured: bool
    ok: bool
    error: str | None = None
    # ISO-timestamp for hvornår Plex-biblioteket sidst blev hentet — sammen
    # med cache_ttl_seconds kan frontend/admin se om et badge er "friskt".
    fetched_at: str | None = None
    cache_ttl_seconds: int = 0
    items: dict[str, PlexAvailability] = Field(default_factory=dict)


class PlexSectionInfo(BaseModel):
    key: str
    title: str
    type: str
    item_count: int
    # Hvor mange af sektionens elementer der overhovedet havde et TMDb-guid.
    # Er dette 0 på en ellers fyldt sektion, bruger sektionen en agent uden
    # TMDb-id'er, og matchning falder tilbage på titel+år — netop den slags
    # der ellers ligner "Plex virker ikke".
    with_tmdb_guid: int
    with_imdb_guid: int


class PlexUnmatchedItem(BaseModel):
    title: str
    year: int | None = None
    tmdb_id: int | None = None


class PlexImportRequest(BaseModel):
    """Feature #90. `dry_run` er default `True`: en import kan oprette
    hundredvis af poster, så standarden er at vise hvad der *ville* ske.
    Selve udførelsen kræver et eksplicit `dry_run: false`."""

    dry_run: bool = True
    include_movies: bool = True
    include_shows: bool = True
    # Sættes på alt importeret, så resultatet kan filtreres frem i
    # biblioteket og rulles tilbage igen hvis det ikke blev som forventet.
    # Tom streng = intet tag.
    tag: str = Field(default="Plex-import", max_length=60)


class PlexImportItem(BaseModel):
    kind: PlexKind
    title: str
    year: int | None = None
    tmdb_id: int | None = None
    # Hvordan TMDb-id'et blev fundet: direkte fra Plex' guid, eller via en
    # titel-søgning på TMDb. Det sidste er det svageste led i importen, så
    # det skal kunne ses på hvert enkelt element i forhåndsvisningen.
    resolved_via: Literal["plex_guid", "tmdb_search"] | None = None
    # Feature #91 — formatet udledt af Plex' opløsning. For film kendes det
    # allerede i forhåndsvisningen (opløsningen står i sektions-listen); for
    # serier ligger den på episoderne og hentes først ved selve importen, så
    # her er feltet tomt indtil da.
    format: str | None = None
    # BUGS.md #52 — True når Plex ikke kunne oplyse opløsningen, og formatet
    # derfor faldt tilbage til D-1080 i stedet for at blive udledt.
    # Vises i forhåndsvisningen, så man ved hvilke der bør efterses.
    format_is_fallback: bool = False
    # Kun sat når elementet ikke kunne importeres.
    reason: str | None = None


class PlexImportResult(BaseModel):
    dry_run: bool
    ok: bool
    error: str | None = None
    # Alt Plex har, som vi ikke har i forvejen, og som kunne opløses til et
    # TMDb-id. Ved dry_run er det forslaget; ellers er det det udførte.
    imported: list[PlexImportItem] = Field(default_factory=list)
    # Fandtes allerede i biblioteket — talt, ikke listet, da det typisk er
    # hele den eksisterende samling og ikke noget man skal handle på.
    already_present: int = 0
    # Kunne ikke opløses til en entydig TMDb-titel. Listes, fordi det er
    # præcis dem man selv skal tilføje bagefter.
    unmatched: list[PlexImportItem] = Field(default_factory=list)
    # Opløst fint, men selve oprettelsen fejlede (TMDb nede for netop den
    # titel, en database-fejl). Adskilt fra `unmatched`, som er en anden
    # slags problem med en anden løsning.
    failed: list[PlexImportItem] = Field(default_factory=list)
    # True hvis TMDb rate-limitede os undervejs og batchen blev afbrudt —
    # resten kan hentes ved at køre importen igen om lidt.
    stopped_early: bool = False


class PlexDiagnostics(BaseModel):
    """Feature #88's fejlsøgnings-endpoint. Svarer på de tre spørgsmål man
    reelt stiller når badges mangler: (1) kan vi overhovedet nå serveren,
    (2) ser vi de sektioner og det antal elementer vi forventer, og (3)
    hvor mange af *vores* film/serier matchede — og hvilke gjorde ikke."""

    configured: bool
    server_url: str
    token_configured: bool
    ok: bool
    error: str | None = None
    server_name: str | None = None
    server_version: str | None = None
    machine_identifier: str | None = None
    sections: list[PlexSectionInfo] = Field(default_factory=list)
    plex_movie_count: int = 0
    plex_show_count: int = 0
    library_movie_count: int = 0
    library_show_count: int = 0
    matched_movies: int = 0
    matched_shows: int = 0
    matched_by_tmdb: int = 0
    matched_by_title: int = 0
    # De første elementer fra *vores* bibliotek der ikke kunne matches — det
    # er dem man skal kigge på i Plex for at forstå hvorfor.
    unmatched_movies: list[PlexUnmatchedItem] = Field(default_factory=list)
    unmatched_shows: list[PlexUnmatchedItem] = Field(default_factory=list)
    fetched_at: str | None = None
    cache_age_seconds: int | None = None
    cache_ttl_seconds: int = 0
    duration_ms: int | None = None
