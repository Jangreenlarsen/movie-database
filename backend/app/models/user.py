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
    # Feature #80 — an admin can lock out an already-active account without
    # deleting it (e.g. someone leaving, or a suspected compromised login).
    # Blocks login/API access exactly like PENDING/REJECTED (see
    # api.deps.get_current_user); distinct from REJECTED so the audit log
    # and the user's own status message don't conflate "your registration
    # was declined" with "an admin disabled your account afterwards".
    DISABLED = "disabled"


class VisibleFields(BaseModel):
    year: bool = True
    tags: bool = True
    format: bool = False
    audio_types: bool = False
    media_type: bool = False
    rating: bool = False
    runtime: bool = False
    # Feature #88 — "ligger i Plex"-badget. Fra som standard: det er en
    # oplysning der kun giver mening for dem der faktisk har en Plex-server,
    # og et badge der aldrig kan blive sandt er kun støj for alle andre.
    plex: bool = False
    # Feature #113 — genrer som kort-badge, samme "Vis felter"-mønster som
    # de øvrige felter ovenfor.
    genres: bool = False


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

# Feature #108 — grid (poster-kort, som hidtil) eller liste (kompakte
# rækker). Samme fælles-for-begge-faner begrundelse som CardSize ovenfor.
ViewMode = Literal["grid", "list"]

# Feature #89 — UI-sprog pr. bruger. Dansk er kildesproget (al tekst er
# skrevet på dansk først), så det er også standarden; engelsk er tilvalget.
Language = Literal["da", "en"]

# Feature #110 — kun de to valg brugeren selv vælger imellem. `None` (feltets
# default) er bevidst en tredje, ikke-eksponeret tilstand: "følg systemets
# prefers-color-scheme". CSS'en i index.css har allerede fulde
# :root[data-theme="light"]/[data-theme="dark"]-blokke plus en
# prefers-color-scheme-fallback — uden et `None`-mønster ville enhver
# eksisterende bruger med et mørkt system pludselig blive tvunget til lyst
# tema den dag dette felt fik en fast standardværdi.
Theme = Literal["light", "dark"]


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
    # Grid- eller listevisning (feature #108) — samme fælles-for-begge-faner
    # begrundelse som card_size lige ovenfor.
    view_mode: ViewMode = "grid"
    # Antal film/serier pr. side i biblioteksvisningen (feature #15) — én
    # fælles indstilling for begge faner, samme begrundelse som card_size.
    page_size: int = 50
    # UI-sprog (feature #89). Gemt pr. bruger frem for i browseren (Jans valg
    # 2026-08-08), så sproget følger med på tværs af iPhone og PC i stedet for
    # at skulle vælges forfra på hver enhed.
    language: Language = "da"
    # Feature #110 — se Theme-kommentaren ovenfor for hvorfor default er
    # None og ikke "light".
    theme: Theme | None = None


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
    view_mode: ViewMode | None = None
    page_size: int | None = Field(default=None, ge=1, le=500)
    language: Language | None = None
    theme: Theme | None = None


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    # Feature #97 — sproget valgt i login-boksen, så en ny konto starter på
    # det sprog brugeren allerede har valgt frem for altid på dansk.
    # Valgfrit: ældre klienter og API-kald uden feltet får kildesproget.
    language: Language | None = None

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, value: str) -> str:
        """BUGS.md #54 — beskeden nævner e-mail eksplicit, fordi det er det
        folk faktisk prøver. Brugernavnet vises for alle andre i portalen
        ("Registreret af", "Ønsket af", audit-loggen), så en e-mail som
        brugernavn ville gøre adressen synlig for alle — reglen er bevaret
        med vilje (Jans valg 2026-08-09), kun forklaringen er blevet
        brugbar."""
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Brugernavn må kun indeholde bogstaver, tal, - og _ "
                "(en e-mailadresse kan derfor ikke bruges som brugernavn)"
            )
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
    # "pending" is never settable via this endpoint — a user can't be put
    # back into the approval queue. Which of the other three is actually
    # reachable from the target's *current* status is enforced in
    # auth_service.update_user_status (feature #66/#80), not here — e.g.
    # "active" only makes sense coming from "pending" or "disabled".
    status: Literal["active", "rejected", "disabled"]


class User(BaseModel):
    id: str
    username: str
    role: UserRole
    status: UserStatus
    settings: UserSettings
    created_at: datetime
