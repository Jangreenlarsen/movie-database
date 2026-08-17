from typing import Literal

from pydantic import BaseModel, Field

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


# Skriv-kun: "source" fortæller hvorfra den *aktive* nøgle kommer, men den
# faktiske værdi returneres aldrig til frontend (jf. CLAUDE.md regel 6).
KeySource = Literal["env", "custom", "unset"]


class ApiKeyStatus(BaseModel):
    configured: bool
    source: KeySource


# De eneste nøgler der har et rigtigt eksternt testkald bag sig (feature #75)
# — Plex har sin egen tilgængeligheds-tjek pr. film og er bevidst udeladt
# her, for ikke at duplikere den mekanisme.
TestableApiKey = Literal[
    "tmdb_api_token", "discogs_token", "upcdatabase_token", "ean_search_api_key", "omdb_api_key"
]


class ApiKeyTestResult(BaseModel):
    ok: bool
    message: str


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
