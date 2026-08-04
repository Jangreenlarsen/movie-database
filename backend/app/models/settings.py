from typing import Literal

from pydantic import BaseModel, Field

from app.models.scan import BarcodeSource


class SerialNumberConfig(BaseModel):
    start_number: int = Field(default=1, ge=1)
    increment: int = Field(default=1, ge=1)
    padding_width: int = Field(default=0, ge=0, le=10)


class SerialNumberConfigUpdate(BaseModel):
    start_number: int | None = Field(default=None, ge=1)
    increment: int | None = Field(default=None, ge=1)
    padding_width: int | None = Field(default=None, ge=0, le=10)


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
