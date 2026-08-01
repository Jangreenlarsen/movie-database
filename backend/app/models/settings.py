from typing import Literal

from pydantic import BaseModel, Field


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


class SystemSettingsStatus(BaseModel):
    tmdb_api_token: ApiKeyStatus
    upc_api_key: ApiKeyStatus
    discogs_token: ApiKeyStatus
    plex_token: ApiKeyStatus
    # Ikke en hemmelighed (bare en LAN-serveradresse) — returneres derfor med
    # sin faktiske værdi, i modsætning til de fire ovenfor (feature #45).
    plex_server_url: str


class SystemSettingsUpdate(BaseModel):
    """`None`/omitted = don't touch. Empty string = explicitly clear the
    custom override and fall back to `.env` again. Any other string = set a
    new custom value."""

    tmdb_api_token: str | None = Field(default=None, max_length=500)
    upc_api_key: str | None = Field(default=None, max_length=500)
    discogs_token: str | None = Field(default=None, max_length=500)
    plex_token: str | None = Field(default=None, max_length=500)
    plex_server_url: str | None = Field(default=None, max_length=500)
