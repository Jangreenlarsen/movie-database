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
    # Feature #72 — read-only: can browse/search the film-/TV-library and
    # the public Voldby BIO page, and change their own password, but can't
    # create/edit/delete anything. Enforced in the backend (see
    # api.deps.require_not_guest), not just hidden in the UI.
    GUEST = "guest"


class UserStatus(str, Enum):
    # Feature #66 — every account except the very first (which bootstraps
    # itself as ACTIVE admin, see auth_service.register) starts PENDING and
    # cannot use anything beyond GET /api/users/me until an admin approves it.
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"


class VisibleFields(BaseModel):
    year: bool = True
    tags: bool = True
    format: bool = False
    audio_types: bool = False
    media_type: bool = False
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


CardSize = Literal["small", "medium", "large"]


class UserSettings(BaseModel):
    sort_field: str | None = None
    sort_direction: str | None = None
    visible_fields: VisibleFields = Field(default_factory=VisibleFields)
    sort_levels: list[SortLevel] = Field(default_factory=list)
    sort_presets: list[SortPreset] = Field(default_factory=list)
    # TV-serier har egne visnings-/sorterings-indstillinger, adskilt fra
    # filmenes (feature #52) — samme model-shapes genbruges (samme
    # VisibleFields/SortLevel/SortPreset), kun opbevaringen er separat, da
    # de to faners relevante felter/sorteringsmuligheder ikke er identiske.
    tv_visible_fields: VisibleFields = Field(default_factory=VisibleFields)
    tv_sort_levels: list[SortLevel] = Field(default_factory=list)
    tv_sort_presets: list[SortPreset] = Field(default_factory=list)
    # Poster-kortstørrelse i biblioteksvisningerne (feature #59) — én fælles
    # indstilling for både Film- og TV-serie-fanen (Jans bekræftede valg
    # 2026-08-02), i modsætning til visible_fields/sort_* ovenfor som er
    # bevidst adskilt pr. fane — kortstørrelse er en ren visuel præference,
    # ikke indholds-specifik.
    card_size: CardSize = "medium"
    # Antal film/serier pr. side i biblioteksvisningen (feature #15) — én
    # fælles indstilling for begge faner, samme begrundelse som card_size.
    page_size: int = 50


class UserSettingsUpdate(BaseModel):
    sort_field: str | None = None
    sort_direction: str | None = None
    visible_fields: VisibleFields | None = None
    sort_levels: list[SortLevel] | None = None
    sort_presets: list[SortPreset] | None = None
    tv_visible_fields: VisibleFields | None = None
    tv_sort_levels: list[SortLevel] | None = None
    tv_sort_presets: list[SortPreset] | None = None
    card_size: CardSize | None = None
    page_size: int | None = Field(default=None, ge=1, le=500)


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


class UserStatusUpdate(BaseModel):
    # Only these two are settable via the endpoint — a user can't be set
    # back to "pending" once approved/rejected.
    status: Literal["active", "rejected"]


class User(BaseModel):
    id: str
    username: str
    role: UserRole
    status: UserStatus
    settings: UserSettings
    created_at: datetime
