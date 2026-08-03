from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.errors import (
    InvalidCredentialsError,
    LastAdminError,
    UserNotFoundError,
    UsernameTakenError,
    UserNotPendingError,
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
        role=document.get("role", UserRole.STANDARD),
        status=document.get("status", UserStatus.ACTIVE),
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
    # account after that starts as a standard, PENDING user (feature #66)
    # and can't do anything beyond GET /api/users/me until an admin approves
    # it. Without this special case the very first admin would start
    # pending too, with no other admin ever able to log in and approve them
    # — a permanent lockout (CLAUDE.md regel 16).
    is_first_user = await user_repository.count(db) == 0
    document = {
        "username": payload.username,
        "username_normalized": _normalize_username(payload.username),
        "password_hash": hash_password(payload.password),
        "role": UserRole.ADMIN if is_first_user else UserRole.STANDARD,
        "status": UserStatus.ACTIVE if is_first_user else UserStatus.PENDING,
        "settings": user_repository.DEFAULT_SETTINGS,
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
    await user_repository.set_password_hash(db, user_id, hash_password(payload.new_password))


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

    is_demoting_admin = target.get("role") == UserRole.ADMIN.value and role != UserRole.ADMIN
    if is_demoting_admin:
        admin_count = await user_repository.count_by_role(db, UserRole.ADMIN.value)
        if admin_count <= 1:
            raise LastAdminError()

    updated = await user_repository.set_role(db, user_id, role.value)
    return to_user_model(updated)


async def update_user_status(db: AsyncIOMotorDatabase, user_id: str, status: str) -> User:
    """Approve (`active`) or reject (`rejected`) a pending registration
    (feature #66). Only allowed while the target is still `pending` —
    otherwise a stray click could silently lock out an already-active user
    (e.g. rejecting an admin by mistake)."""
    target = await user_repository.find_by_id(db, user_id)
    if target is None:
        raise UserNotFoundError(user_id)
    if target.get("status", UserStatus.ACTIVE.value) != UserStatus.PENDING.value:
        raise UserNotPendingError(user_id)

    updated = await user_repository.set_status(db, user_id, status)
    return to_user_model(updated)
