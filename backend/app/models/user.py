from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import settings

# bcrypt only considers the first 72 bytes of a password — anything beyond
# that is silently ignored, so two different long passwords sharing the same
# first 72 bytes would hash identically. Enforce that limit explicitly
# instead of letting bcrypt truncate without telling anyone.
_BCRYPT_MAX_BYTES = 72


def _validate_bcrypt_byte_length(value: str) -> str:
    if len(value.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"Adgangskode må maks fylde {_BCRYPT_MAX_BYTES} byte")
    return value


# Feature #174 — adgangskode-politik (Jan: "vi skal have en password politik
# config del i setting"). Læser `settings` (den samme in-memory-singleton
# system_settings_service.update_password_policy synkroniserer) direkte ved
# hvert kald, i stedet for en statisk Pydantic `Field(min_length=...)` — en
# admin-konfigureret politik skal slå igennem med det samme, ikke kun ved
# genstart. Brugt af BÅDE UserRegister.password og PasswordChange.new_password,
# så politikken håndhæves ens uanset hvilken af de to veje en adgangskode
# sættes ad (CLAUDE.md regel 16 — "regler der kun gælder én gren").
def validate_password_policy(value: str) -> str:
    if len(value) < settings.password_min_length:
        raise ValueError(
            f"Adgangskode skal være mindst {settings.password_min_length} tegn"
        )
    if settings.password_require_uppercase and not any(c.isupper() for c in value):
        raise ValueError("Adgangskode skal indeholde mindst ét stort bogstav")
    if settings.password_require_lowercase and not any(c.islower() for c in value):
        raise ValueError("Adgangskode skal indeholde mindst ét lille bogstav")
    if settings.password_require_digit and not any(c.isdigit() for c in value):
        raise ValueError("Adgangskode skal indeholde mindst ét tal")
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
    # TV-serier har egne visnings-/sorterings-indstillinger, adskilt fra
    # filmenes (feature #52) — samme model-shapes genbruges (samme
    # VisibleFields/SortLevel), kun opbevaringen er separat, da de to
    # faners relevante felter/sorteringsmuligheder ikke er identiske.
    tv_visible_fields: VisibleFields = Field(default_factory=VisibleFields)
    tv_sort_levels: list[SortLevel] = Field(default_factory=list)
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
    tv_visible_fields: VisibleFields | None = None
    tv_sort_levels: list[SortLevel] | None = None
    card_size: CardSize | None = None
    view_mode: ViewMode | None = None
    page_size: int | None = Field(default=None, ge=1, le=500)
    language: Language | None = None
    theme: Theme | None = None


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    # Feature #174 — den reelle minimum-længde er nu dynamisk (læses fra
    # settings.password_min_length af validate_password_policy nedenfor),
    # så det statiske Field-min_length her er kun en lav bundgrænse ("ikke
    # tom"), ikke selve politikken.
    password: str = Field(min_length=1, max_length=128)
    # Feature #140 — fuldt navn, så en admin kan se HVEM der beder om adgang før
    # de godkendes. Håndhæves som påkrævet i selve registrerings-formularen
    # (Login.jsx + den offentlige /bio-login); modellen holder feltet valgfrit,
    # så den eksisterende API-kontrakt (og hele testsuiten, der registrerer uden
    # feltet) ikke brydes — det er et identitets-/oplysningsfelt, ikke et
    # sikkerhedsfelt. Tomt/kun-mellemrum normaliseres til None.
    full_name: str | None = Field(default=None, max_length=100)
    # Feature #199-opfølgning (Jan: "opret ny user tager ikke en email adr.,
    # skal vi lige have den del af system til at gøre") — valgfri, så man
    # kan sætte sin e-mail med det samme ved oprettelse i stedet for at
    # skulle huske det bagefter i Indstillinger → Konto (UserEmailUpdate,
    # feature #197). Samme trim/tom-til-None-mønster som full_name_clean
    # nedenfor, kørt FØR selve EmailStr-formatvalideringen (mode="before"),
    # så et tomt felt tolkes som "intet sat", ikke som en 422-fejl.
    email: EmailStr | None = Field(default=None, max_length=254)
    # Feature #97 — sproget valgt i login-boksen, så en ny konto starter på
    # det sprog brugeren allerede har valgt frem for altid på dansk.
    # Valgfrit: ældre klienter og API-kald uden feltet får kildesproget.
    language: Language | None = None

    @field_validator("full_name")
    @classmethod
    def full_name_clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("email", mode="before")
    @classmethod
    def email_blank_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

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
    def password_policy(cls, value: str) -> str:
        return validate_password_policy(value)

    @field_validator("password")
    @classmethod
    def password_bcrypt_length(cls, value: str) -> str:
        return _validate_bcrypt_byte_length(value)


class UserLogin(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    # Feature #174 — se UserRegister.password's kommentar: den rigtige
    # bundgrænse håndhæves dynamisk af validate_password_policy nedenfor.
    new_password: str = Field(min_length=1, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_policy(cls, value: str) -> str:
        return validate_password_policy(value)

    @field_validator("new_password")
    @classmethod
    def new_password_bcrypt_length(cls, value: str) -> str:
        return _validate_bcrypt_byte_length(value)


class ForgotPasswordRequest(BaseModel):
    """Feature #205 — selvbetjent password-reset via e-mail."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    # Samme politik/bcrypt-grænse som PasswordChange.new_password ovenfor —
    # en nulstillet adgangskode skal opfylde nøjagtig samme krav som en
    # almindeligt skiftet.
    new_password: str = Field(min_length=1, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_policy(cls, value: str) -> str:
        return validate_password_policy(value)

    @field_validator("new_password")
    @classmethod
    def new_password_bcrypt_length(cls, value: str) -> str:
        return _validate_bcrypt_byte_length(value)


class ForgotPasswordResponse(BaseModel):
    """Bevidst ÉN fast besked uanset om e-mailen rent faktisk findes i
    systemet (anti-enumerering) — se auth_service.request_password_reset."""

    message: str


class PasswordResetResult(BaseModel):
    """Feature #171 — admin-assisteret password recovery (ingen e-mail-
    system). Den nye adgangskode returneres i klartekst PRÆCIS denne ene
    gang, som en almindelig HTTPS-respons til den admin der selv udløste
    handlingen (aldrig gemt/logget nogen steder — hverken her eller i
    audit-loggen, som kun optegner AT en nulstilling skete og for hvem)."""

    username: str
    new_password: str


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserStatusUpdate(BaseModel):
    # "pending" is never settable via this endpoint — a user can't be put
    # back into the approval queue. Which of the other three is actually
    # reachable from the target's *current* status is enforced in
    # auth_service.update_user_status (feature #66/#80), not here — e.g.
    # "active" only makes sense coming from "pending" or "disabled".
    status: Literal["active", "rejected", "disabled"]


# Feature #178-opfølgning (Jan: "sæt op i users styring hvem kan se og bruge
# vis iplex/spil i plex i detajle for film/tv") — pr.-bruger, ikke rolle-
# baseret (Jans eksplicitte valg). Kun "Afspil i Plex"-linket (feature #45/
# #88) er omfattet, ikke Plex-badget på selve kortet.
class UserPlexPlayUpdate(BaseModel):
    enabled: bool


class UserEmailUpdate(BaseModel):
    """Feature #197 — sat af brugeren selv eller en admin (se
    auth_service._assert_can_edit_email), udelukkende brugt til udgående
    e-mail-notifikationer. `None`/tom streng rydder feltet igen — samme
    trim/tom-til-None-mønster som UserRegister.full_name_clean, kørt FØR
    Pydantics egen EmailStr-formatvalidering (mode="before"), så en
    tomt-udfyldt formular ikke fejler som "ugyldig e-mail" i stedet for
    bare at blive tolket som "ryd feltet"."""

    email: EmailStr | None = Field(default=None, max_length=254)

    @field_validator("email", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class User(BaseModel):
    id: str
    username: str
    # Feature #140 — vises for admin (bruger-listen) og for brugeren selv
    # (/users/me). None på konti oprettet før feltet eller via API uden det.
    full_name: str | None = None
    # Feature #197 — valgfri, sat af brugeren selv (Indstillinger → Konto)
    # eller en admin, brugt udelukkende til udgående e-mail-notifikationer.
    # Plain `str` på læse-siden med vilje (ikke `EmailStr`) — allerede gemte,
    # tidligere validerede data skal ikke revalideres ved hver læsning.
    email: str | None = None
    role: UserRole
    status: UserStatus
    # Feature #172 — sat af en admin-nulstilling (#171), ryddet igen af en
    # vellykket adgangskodeskift (egen eller tvungen). Frontend viser en
    # blokerende "skift adgangskode"-skærm så længe denne er sand — se
    # api.deps.get_current_user, som håndhæver det samme i backend.
    must_change_password: bool = False
    # Feature #178-opfølgning — pr.-bruger til/fra for "Afspil i Plex"-linket
    # i film-/serie-detaljevinduet. Default `true`: en helt ny restriktion på
    # en feature alle hidtil har kunnet bruge, så eksisterende konti (uden
    # feltet i deres dokument) skal ikke stille og roligt miste adgang — en
    # admin slår den fra eksplicit pr. bruger, det er ikke en opt-in-liste.
    plex_play_enabled: bool = True
    settings: UserSettings
    created_at: datetime
