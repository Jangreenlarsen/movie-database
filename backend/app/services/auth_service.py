import secrets
import string
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.errors import (
    CannotTargetSelfError,
    InvalidCredentialsError,
    InvalidUserStatusTransitionError,
    LastAdminError,
    NotAuthorizedError,
    UserNotFoundError,
    UsernameTakenError,
)
from app.core.security import hash_password, verify_password
from app.models.user import (
    PasswordChange,
    User,
    UserLogin,
    UserRegister,
    UserRole,
    UserSettings,
    UserSettingsUpdate,
    UserStatus,
)
from app.repositories import user_repository


def to_user_model(document: dict) -> User:
    merged_settings = {**user_repository.DEFAULT_SETTINGS, **document.get("settings", {})}
    return User(
        id=str(document["_id"]),
        username=document["username"],
        full_name=document.get("full_name"),
        email=document.get("email"),
        role=document.get("role", UserRole.STANDARD),
        status=document.get("status", UserStatus.ACTIVE),
        must_change_password=document.get("must_change_password", False),
        plex_play_enabled=document.get("plex_play_enabled", True),
        settings=UserSettings(**merged_settings),
        created_at=document["created_at"],
    )


def _normalize_username(username: str) -> str:
    """Case-insensitive identity key — "jgl"/"Jgl"/"JGL" are the same
    account. Login/uniqueness compare on this; the originally-typed casing
    is still stored and shown as-is (same "normalize for comparison, keep
    original for display" pattern as tag_service.normalize/resolve_tags).
    See BUGS.md #21."""
    return username.lower()


async def register(db: AsyncIOMotorDatabase, payload: UserRegister) -> User:
    # Bootstrapping: the very first account ever created has no one to grant
    # it admin rights or approve it, so it grants itself both — every
    # account after that starts as a PENDING user (feature #66) and can't
    # do anything beyond GET /api/users/me until an admin approves it.
    # Without this special case the very first admin would start pending
    # too, with no other admin ever able to log in and approve them — a
    # permanent lockout (CLAUDE.md regel 16).
    #
    # Feature #175 (Jan: "ved nye users oprettelse skal de som default
    # sættes som guest i portal og ikke som nu standart user") — a fresh
    # signup now defaults to the read-only guest role (feature #72)
    # instead of standard. An admin still reviews every pending signup
    # (feature #66) and can promote them to standard/admin from Indstillinger
    # → Brugere exactly as before; this only tightens the *default* they
    # land on once approved, not the approval flow itself.
    is_first_user = await user_repository.count(db) == 0
    document = {
        "username": payload.username,
        "username_normalized": _normalize_username(payload.username),
        # Feature #140 — trimmet/None-normaliseret af UserRegister.full_name_clean.
        "full_name": payload.full_name,
        # Feature #199-opfølgning — samme trim/tom-til-None-normalisering,
        # se UserRegister.email_blank_to_none.
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "role": UserRole.ADMIN if is_first_user else UserRole.GUEST,
        "status": UserStatus.ACTIVE if is_first_user else UserStatus.PENDING,
        "plex_play_enabled": True,
        # Feature #97 — sprogvalget fra login-boksen bliver kontoens
        # startsprog. Kopi frem for reference: DEFAULT_SETTINGS er et
        # modul-globalt dict, og en ændring her ville ellers ramme hver
        # eneste efterfølgende registrering.
        "settings": {
            **user_repository.DEFAULT_SETTINGS,
            **({"language": payload.language} if payload.language else {}),
        },
        "created_at": datetime.now(timezone.utc),
    }
    try:
        created = await user_repository.insert(db, document)
    except DuplicateKeyError as exc:
        raise UsernameTakenError(payload.username) from exc
    return to_user_model(created)


async def authenticate(db: AsyncIOMotorDatabase, payload: UserLogin) -> User:
    document = await user_repository.find_by_username_normalized(
        db, _normalize_username(payload.username)
    )
    if document is None or not verify_password(payload.password, document["password_hash"]):
        raise InvalidCredentialsError()
    return to_user_model(document)


async def update_settings(
    db: AsyncIOMotorDatabase, user_id: str, payload: UserSettingsUpdate
) -> User:
    """Only the fields actually present in `payload` are touched — via
    dotted-path `$set`s in the repository, not a read-full-then-overwrite of
    the whole `settings` sub-document. The Library page fires several of
    these PATCHes in quick succession (e.g. adjusting sort levels, then
    saving a preset) with no client-side queuing, so a read-modify-write
    here would silently lose whichever update's write landed first once a
    later one overwrote it wholesale with a stale snapshot. See BUGS.md."""
    updates = payload.model_dump(exclude_unset=True, mode="json")
    updated = await user_repository.update_settings(db, user_id, updates)
    if updated is None:
        raise UserNotFoundError(user_id)
    return to_user_model(updated)


async def change_password(
    db: AsyncIOMotorDatabase, user_id: str, payload: PasswordChange
) -> None:
    document = await user_repository.find_by_id(db, user_id)
    if document is None or not verify_password(
        payload.current_password, document["password_hash"]
    ):
        raise InvalidCredentialsError()
    # Feature #172 — any successful self-service change (voluntary, or the
    # forced one after an admin reset) clears must_change_password, even if
    # it was already False — the requirement, if any, is satisfied either way.
    await user_repository.set_password_hash(
        db, user_id, hash_password(payload.new_password), must_change_password=False
    )


# Feature #171 — admin-assisteret password recovery (ingen e-mail-system,
# Jans eksplicitte ønske). Undgår tegn der let forveksles ved oplæsning/
# aflæsning over telefon eller chat (0/O, 1/l/I) — adgangskoden skal jo
# relæes til brugeren uden om selve appen. 12 tegn fra et ~54-tegns alfabet
# giver rigelig entropi (langt over `PasswordChange`s standard min_length=8)
# uden at være unødigt besværlig at skrive af.
_TEMP_PASSWORD_ALPHABET = "".join(
    c for c in string.ascii_letters + string.digits if c not in "0O1lI"
)
_TEMP_PASSWORD_UPPERCASE = [c for c in _TEMP_PASSWORD_ALPHABET if c.isupper()]
_TEMP_PASSWORD_LOWERCASE = [c for c in _TEMP_PASSWORD_ALPHABET if c.islower()]
_TEMP_PASSWORD_DIGITS = [c for c in _TEMP_PASSWORD_ALPHABET if c.isdigit()]


def _generate_temporary_password() -> str:
    """Feature #174 — den genererede kode skal selv overholde den
    admin-konfigurerede politik, ikke kun de almindelige register/skift-veje
    (CLAUDE.md regel 16 — "regler der kun gælder én gren"). Længden følger
    politikkens minimum PRÆCIST — BUGS.md #75 (Jan, testet live: satte
    min-længden til 6, men fik stadig en 12-tegns kode udleveret til
    kopi/paste). Første udgave brugte bevidst `max(12, ...)` for aldrig at
    generere en svagere kode end den hidtidige faste værdi, men det var en
    antagelse Claude selv tilføjede uden at være bedt om det — Jan vil have
    den udleverede kode matche det han rent faktisk satte, ikke en skjult
    egen-valgt bundgrænse. `PasswordPolicyUpdate.password_min_length`s
    egen `ge=6`-grænse er bundgrænsen nu. Et påkrævet tegn-klasse (stort/
    lille bogstav, tal) INDSÆTTES stadig eksplicit i stedet for at stole på
    at nok tilfældige tegn statistisk sandsynligvis rammer alle klasser —
    "sandsynligt" er ikke "garanteret"."""
    length = settings.password_min_length

    required = []
    if settings.password_require_uppercase:
        required.append(secrets.choice(_TEMP_PASSWORD_UPPERCASE))
    if settings.password_require_lowercase:
        required.append(secrets.choice(_TEMP_PASSWORD_LOWERCASE))
    if settings.password_require_digit:
        required.append(secrets.choice(_TEMP_PASSWORD_DIGITS))

    remaining = [secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(length - len(required))]
    password_chars = required + remaining
    # De påkrævede tegn ville ellers altid stå allerførst — bland positionen
    # med samme kryptografisk tilfældige kilde som resten af genereringen.
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)


async def admin_reset_password(db: AsyncIOMotorDatabase, user_id: str) -> tuple[str, str]:
    """Feature #171 — en admin nulstiller en anden brugers adgangskode til
    en tilfældig, midlertidig værdi (ingen e-mail-baseret "glemt adgangskode"
    findes, jf. Jans ønske) og relæer den til brugeren selv, uden om appen
    (telefon, chat, personligt). Returnerer (username, ny_adgangskode) —
    adgangskoden gemmes/logges aldrig i klartekst noget sted efter dette
    kald returnerer (heller ikke i audit-loggen, kun AT det skete).

    Feature #172 (Jans udtrykkelige krav, "det skal være udfravigeligt") —
    sætter samtidig must_change_password, så den midlertidige kode kun kan
    bruges til selve login'et: `api.deps.get_current_user` blokerer alt
    andet indtil brugeren selv har sat en ny adgangskode."""
    target = await user_repository.find_by_id(db, user_id)
    if target is None:
        raise UserNotFoundError(user_id)
    new_password = _generate_temporary_password()
    await user_repository.set_password_hash(
        db, user_id, hash_password(new_password), must_change_password=True
    )
    return target["username"], new_password


async def verify_current_password(db: AsyncIOMotorDatabase, user_id: str, current_password: str) -> None:
    """Re-checks the acting admin's own password as a stronger confirmation
    step for the most irreversible admin actions (feature #67's database
    reset) — same check as `change_password`, factored out since it isn't
    itself changing anything here."""
    document = await user_repository.find_by_id(db, user_id)
    if document is None or not verify_password(current_password, document["password_hash"]):
        raise InvalidCredentialsError()


async def list_users(db: AsyncIOMotorDatabase) -> list[User]:
    documents = await user_repository.list_all(db)
    return [to_user_model(doc) for doc in documents]


async def update_user_role(db: AsyncIOMotorDatabase, user_id: str, role: UserRole) -> User:
    target = await user_repository.find_by_id(db, user_id)
    if target is None:
        raise UserNotFoundError(user_id)

    # BUGS.md #40 — the guard must count admins who can actually LOG IN, not
    # every document that merely has `role: "admin"`. Since feature #80 a
    # disabled (or pending/rejected) admin still carries the admin role while
    # being unable to authenticate at all, so counting those made the guard
    # believe a spare admin existed and allowed the last *usable* one to be
    # demoted — an unrecoverable lockout, since `register`'s bootstrap only
    # re-grants admin when `users` is completely empty. Demoting an already
    # non-active admin stays allowed: it can't reduce the usable-admin count.
    is_demoting_admin = target.get("role") == UserRole.ADMIN.value and role != UserRole.ADMIN
    target_is_active = target.get("status", UserStatus.ACTIVE.value) == UserStatus.ACTIVE.value
    if is_demoting_admin and target_is_active:
        admin_count = await user_repository.count_active_admins(db)
        if admin_count <= 1:
            raise LastAdminError()

    updated = await user_repository.set_role(db, user_id, role.value)
    return to_user_model(updated)



# Feature #66/#80 — which status transitions are reachable depends on the
# target's *current* status. "pending" is never a settable target (a user
# can't be put back into the approval queue), and each of the other three
# only makes sense coming from a specific starting point — e.g. you can't
# "activate" a rejected registration, and can't "disable" someone who's
# still pending approval.
_VALID_STATUS_TRANSITIONS = {
    UserStatus.PENDING.value: {UserStatus.ACTIVE.value, UserStatus.REJECTED.value},
    UserStatus.ACTIVE.value: {UserStatus.DISABLED.value},
    UserStatus.DISABLED.value: {UserStatus.ACTIVE.value},
}


async def update_user_status(
    db: AsyncIOMotorDatabase, user_id: str, status: str, requesting_user_id: str
) -> User:
    """Approve/reject a pending registration (feature #66), or
    disable/re-enable an already-active account (feature #80, e.g. someone
    leaving or a suspected compromised login) — without deleting it."""
    target = await user_repository.find_by_id(db, user_id)
    if target is None:
        raise UserNotFoundError(user_id)

    current_status = target.get("status", UserStatus.ACTIVE.value)
    if status not in _VALID_STATUS_TRANSITIONS.get(current_status, set()):
        raise InvalidUserStatusTransitionError(current_status, status)

    if status == UserStatus.DISABLED.value:
        if user_id == requesting_user_id:
            raise CannotTargetSelfError()
        if target.get("role") == UserRole.ADMIN.value:
            admin_count = await user_repository.count_active_admins(db)
            if admin_count <= 1:
                raise LastAdminError()

    updated = await user_repository.set_status(db, user_id, status)
    return to_user_model(updated)


async def update_user_plex_play(db: AsyncIOMotorDatabase, user_id: str, enabled: bool) -> User:
    """Feature #178-opfølgning (Jan: "sæt op i users styring hvem kan se og
    bruge vis iplex/spil i plex i detajle for film/tv") — pr.-bruger til/fra
    for "Afspil i Plex"-linket. Ingen lockout-risiko som ved rolle/status
    (kan ikke gøre nogen ude af stand til at logge ind eller administrere),
    så ingen af de guards role/status-opdateringerne har."""
    target = await user_repository.find_by_id(db, user_id)
    if target is None:
        raise UserNotFoundError(user_id)

    updated = await user_repository.set_plex_play_enabled(db, user_id, enabled)
    return to_user_model(updated)


def _assert_can_edit_email(current_user: dict, user_id: str) -> None:
    """Feature #197 — samme selv-eller-admin-form som
    movie_service._assert_can_edit_serial_number, blot uden dens
    "hvem registrerede den"-gren: her er det brugerens EGEN konto, ikke en
    tredje ressource nogen registrerede. Håndhæves i backend, ikke kun
    ved at skjule et felt i UI'et (CLAUDE.md regel 16)."""
    is_admin = current_user.get("role") == "admin"
    is_self = str(current_user.get("_id")) == user_id
    if not (is_admin or is_self):
        raise NotAuthorizedError("Kun brugeren selv eller en admin kan ændre denne e-mail")


async def update_user_email(
    db: AsyncIOMotorDatabase, user_id: str, email: str | None, current_user: dict
) -> User:
    """Feature #197 — e-mailen bruges udelukkende til udgående
    notifikationer (message_service._send_emails); intet login/identitet
    afhænger af den, i modsætning til username."""
    target = await user_repository.find_by_id(db, user_id)
    if target is None:
        raise UserNotFoundError(user_id)

    _assert_can_edit_email(current_user, user_id)

    updated = await user_repository.set_email(db, user_id, email)
    return to_user_model(updated)


async def delete_user(db: AsyncIOMotorDatabase, user_id: str, requesting_user_id: str) -> User:
    """Feature #80 — permanently removes an account (unlike movies/TV-shows
    there's no soft-delete/archive collection for users; `registered_by`/
    `owner`/audit-log entries store the username as plain text, so nothing
    is orphaned by removing the account). Guarded the same way as disabling:
    can't target yourself, can't remove the last active admin. Returns the
    now-deleted user (as it was just before removal) so the caller can log
    its username without a second lookup."""
    target = await user_repository.find_by_id(db, user_id)
    if target is None:
        raise UserNotFoundError(user_id)
    if user_id == requesting_user_id:
        raise CannotTargetSelfError()
    if (
        target.get("role") == UserRole.ADMIN.value
        and target.get("status", UserStatus.ACTIVE.value) == UserStatus.ACTIVE.value
    ):
        admin_count = await user_repository.count_active_admins(db)
        if admin_count <= 1:
            raise LastAdminError()
    await user_repository.delete(db, user_id)
    return to_user_model(target)
