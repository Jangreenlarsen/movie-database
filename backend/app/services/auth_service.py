from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.errors import (
    InvalidCredentialsError,
    LastAdminError,
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
)
from app.repositories import user_repository


def to_user_model(document: dict) -> User:
    merged_settings = {**user_repository.DEFAULT_SETTINGS, **document.get("settings", {})}
    return User(
        id=str(document["_id"]),
        username=document["username"],
        role=document.get("role", UserRole.STANDARD),
        settings=UserSettings(**merged_settings),
        created_at=document["created_at"],
    )


async def register(db: AsyncIOMotorDatabase, payload: UserRegister) -> User:
    # Bootstrapping: the very first account ever created has no one to grant
    # it admin rights, so it grants itself — every account after that starts
    # as a standard user.
    is_first_user = await user_repository.count(db) == 0
    document = {
        "username": payload.username,
        "password_hash": hash_password(payload.password),
        "role": UserRole.ADMIN if is_first_user else UserRole.STANDARD,
        "settings": user_repository.DEFAULT_SETTINGS,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        created = await user_repository.insert(db, document)
    except DuplicateKeyError as exc:
        raise UsernameTakenError(payload.username) from exc
    return to_user_model(created)


async def authenticate(db: AsyncIOMotorDatabase, payload: UserLogin) -> User:
    document = await user_repository.find_by_username(db, payload.username)
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
