from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# bcrypt only considers the first 72 bytes of a password — anything beyond
# that is silently ignored, so two different long passwords sharing the same
# first 72 bytes would hash identically. Enforce that limit explicitly
# instead of letting bcrypt truncate without telling anyone.
_BCRYPT_MAX_BYTES = 72


def _validate_bcrypt_byte_length(value: str) -> str:
    if len(value.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"Adgangskode må maks fylde {_BCRYPT_MAX_BYTES} byte")
    return value


class UserRole(str, Enum):
    ADMIN = "admin"
    STANDARD = "standard"


class VisibleFields(BaseModel):
    year: bool = True
    tags: bool = True
    format: bool = False
    audio_types: bool = False
    rating: bool = False
    runtime: bool = False


class SortLevel(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "asc"


class SortPreset(BaseModel):
    """A named, saveable "view" — sort levels plus the rest of the library's
    filter state (feature #44). The filter fields are all optional/defaulted
    so presets saved before this feature (sort-only) keep validating and
    simply apply no extra filtering when re-selected."""

    name: str
    levels: list[SortLevel]
    query: str | None = None
    tags: list[str] = Field(default_factory=list)
    formats: list[str] = Field(default_factory=list)
    audio_types: list[str] = Field(default_factory=list)
    media_types: list[str] = Field(default_factory=list)
    watched: bool | None = None


class UserSettings(BaseModel):
    sort_field: str | None = None
    sort_direction: str | None = None
    visible_fields: VisibleFields = Field(default_factory=VisibleFields)
    sort_levels: list[SortLevel] = Field(default_factory=list)
    sort_presets: list[SortPreset] = Field(default_factory=list)


class UserSettingsUpdate(BaseModel):
    sort_field: str | None = None
    sort_direction: str | None = None
    visible_fields: VisibleFields | None = None
    sort_levels: list[SortLevel] | None = None
    sort_presets: list[SortPreset] | None = None


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, value: str) -> str:
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Brugernavn må kun indeholde bogstaver, tal, - og _")
        return value

    @field_validator("password")
    @classmethod
    def password_bcrypt_length(cls, value: str) -> str:
        return _validate_bcrypt_byte_length(value)


class UserLogin(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_bcrypt_length(cls, value: str) -> str:
        return _validate_bcrypt_byte_length(value)


class UserRoleUpdate(BaseModel):
    role: UserRole


class User(BaseModel):
    id: str
    username: str
    role: UserRole
    settings: UserSettings
    created_at: datetime
