from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.scan import BarcodeSource


class FreeSerialNumbers(BaseModel):
    """Feature #131 — de frigjorte (genbrugbare) numre pr. serie, laveste
    først. Fysiske film (M#), fysiske TV-serier (T#) og den delte digitale
    serie (D#)."""

    physical_movies: list[int] = Field(default_factory=list)
    physical_tv: list[int] = Field(default_factory=list)
    digital: list[int] = Field(default_factory=list)


class SerialNumberConfig(BaseModel):
    start_number: int = Field(default=1, ge=1)
    increment: int = Field(default=1, ge=1)
    padding_width: int = Field(default=0, ge=0, le=10)
    # Feature #131 — én fælles til/fra for genbrug af frigjorte numre (alle tre
    # serier). Read-only oversigt over de faktisk ledige numre følger med.
    reuse_freed: bool = False
    free_numbers: FreeSerialNumbers = Field(default_factory=FreeSerialNumbers)


class SerialNumberConfigUpdate(BaseModel):
    start_number: int | None = Field(default=None, ge=1)
    increment: int | None = Field(default=None, ge=1)
    padding_width: int | None = Field(default=None, ge=0, le=10)
    reuse_freed: bool | None = None


class DigitalRenumberResult(BaseModel):
    """Feature #188 — svaret på en engangs-omnummerering af D#-serien til at
    starte fra 1 (retter BUGS.md #81's historiske "1-162 findes ikke"-hul)."""

    renumbered: int


# Skriv-kun: "source" fortæller hvorfra den *aktive* nøgle kommer, men den
# faktiske værdi returneres aldrig til frontend (jf. CLAUDE.md regel 6).
KeySource = Literal["env", "custom", "unset"]


class ApiKeyStatus(BaseModel):
    configured: bool
    source: KeySource


# De eneste nøgler der har et rigtigt eksternt testkald bag sig (feature #75)
# — Plex har sin egen tilgængeligheds-tjek pr. film og er bevidst udeladt
# her, for ikke at duplikere den mekanisme. `anthem_host` (feature #212) er
# ikke en hemmelighed (samme som `plex_server_url`), men "test forbindelse"
# giver lige så god mening for en LAN-enhedsadresse som for en API-nøgle.
TestableApiKey = Literal[
    "tmdb_api_token",
    "discogs_token",
    "upcdatabase_token",
    "ean_search_api_key",
    "omdb_api_key",
    "resend_api_key",
    "anthem_host",
]


class ApiKeyTestResult(BaseModel):
    ok: bool
    message: str


class TestEmailRequest(BaseModel):
    """Feature #199 — modtageradresse for en ægte testmail, adskilt fra
    `test_connection` ovenfor (som kun bekræfter nøglens gyldighed, ikke at
    en mail rent faktisk kan afleveres end-to-end)."""

    to: EmailStr


class SystemSettingsStatus(BaseModel):
    tmdb_api_token: ApiKeyStatus
    discogs_token: ApiKeyStatus
    upcdatabase_token: ApiKeyStatus
    ean_search_api_key: ApiKeyStatus
    omdb_api_key: ApiKeyStatus
    plex_token: ApiKeyStatus
    # Ikke en hemmelighed (bare en LAN-serveradresse) — returneres derfor med
    # sin faktiske værdi, i modsætning til de øvrige ovenfor (feature #45).
    plex_server_url: str
    # Heller ikke en hemmelighed — hvilken stregkode-kilde der prøves først
    # (feature #77), returneres derfor også med sin faktiske værdi.
    primary_barcode_source: BarcodeSource
    # Feature #178 — Shield TV'ets Plex client-id. Ikke en hemmelighed
    # (samme princip som plex_server_url ovenfor).
    plex_shield_client_identifier: str
    # Feature #183 — Anthem AVM 70's IP/port. Heller ikke en hemmelighed.
    anthem_host: str
    anthem_port: int
    # Feature #197 — udgående e-mail (Resend). Nøglen er en rigtig
    # hemmelighed (masket som de øvrige ApiKeyStatus-felter ovenfor);
    # afsenderadressen er det ikke (samme princip som plex_server_url).
    resend_api_key: ApiKeyStatus
    email_from_address: str


class SystemSettingsUpdate(BaseModel):
    """`None`/omitted = don't touch. Empty string = explicitly clear the
    custom override and fall back to `.env` again. Any other string = set a
    new custom value."""

    tmdb_api_token: str | None = Field(default=None, max_length=500)
    discogs_token: str | None = Field(default=None, max_length=500)
    upcdatabase_token: str | None = Field(default=None, max_length=500)
    ean_search_api_key: str | None = Field(default=None, max_length=500)
    omdb_api_key: str | None = Field(default=None, max_length=500)
    plex_token: str | None = Field(default=None, max_length=500)
    plex_server_url: str | None = Field(default=None, max_length=500)
    primary_barcode_source: Literal["", "upcitemdb", "discogs", "upcdatabase", "ean_search"] | None = None
    plex_shield_client_identifier: str | None = Field(default=None, max_length=100)
    anthem_host: str | None = Field(default=None, max_length=255)
    anthem_port: int | None = Field(default=None, ge=1, le=65535)
    resend_api_key: str | None = Field(default=None, max_length=500)
    email_from_address: str | None = Field(default=None, max_length=255)


# Feature #174 — adgangskode-politik (Jan: "vi skal have en password politik
# config del i setting"). Egen lille model-familie i stedet for at presse
# int/bool-felter ind i SystemSettingsUpdate's rent streng-baserede
# "" = ryd-til-.env-mønster ovenfor, som ikke giver mening her (der er intet
# .env-modstykke at falde tilbage til). Deler stadig samme
# `system_settings`-dokument i MongoDB, bare via egne, typede
# repository-funktioner.
class PasswordPolicy(BaseModel):
    password_min_length: int
    password_require_uppercase: bool
    password_require_lowercase: bool
    password_require_digit: bool


class PasswordPolicyUpdate(BaseModel):
    """`None`/omitted = don't touch — i modsætning til SystemSettingsUpdate
    findes der intet "ryd override"-koncept her, kun "sæt til denne værdi",
    da felterne ikke har noget .env at falde tilbage til."""

    password_min_length: int | None = Field(default=None, ge=6, le=64)
    password_require_uppercase: bool | None = None
    password_require_lowercase: bool | None = None
    password_require_digit: bool | None = None


# Feature #177 — kræv dato/tidspunkt ved visningsønsker, til/fra (Jan: "vi
# skal kunne sætte om guest ved film forvisnings ønske skal bruge dato/tid
# eller ikke"). Samme lille model-familie-mønster som PasswordPolicy
# ovenfor. Feature #186 (Jan, 2026-08-20: "angivning af dato/tid for
# forvisning skal gælde for alle roller og ikke kun guest") udvidede den
# fra kun gæster til alle roller — omdøbt fra
# require_preferred_at_for_guests, håndhæves nu ens for alle i
# screening_service uden nogen rolle-særbehandling.
class ScreeningRequestPolicy(BaseModel):
    require_preferred_at: bool


class ScreeningRequestPolicyUpdate(BaseModel):
    require_preferred_at: bool | None = None


# Feature #181 — automatisk periodisk scan af Plex for nye film/serier
# (Jan: "jeg tro tilgengæld at vi skal have en automatisk scan af plex
# media server for ny film og tv serie, i dag er det en manual funktion").
# Samme lille model-familie-mønster som PasswordPolicy/ScreeningRequestPolicy
# ovenfor. Den eksisterende manuelle "Importér fra Plex"-knap (feature #90)
# forbliver uændret ved siden af — denne styrer kun baggrunds-loopet.
class PlexAutoImportPolicy(BaseModel):
    plex_auto_import_enabled: bool
    plex_auto_import_interval_minutes: int
    # Delt med den manuelle "Importér fra Plex"-knap — se config.pys note.
    plex_import_tag: str


class PlexAutoImportPolicyUpdate(BaseModel):
    plex_auto_import_enabled: bool | None = None
    # 15 min til 7 dage — sanity-grænser, ikke en nøje afstemt værdi; formålet
    # er blot at forhindre en tastefejl (0 eller et enormt tal) i at give en
    # meningsløs løkke.
    plex_auto_import_interval_minutes: int | None = Field(default=None, ge=15, le=10080)
    plex_import_tag: str | None = Field(default=None, max_length=60)
