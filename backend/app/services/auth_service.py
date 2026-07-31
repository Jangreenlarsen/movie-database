from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.errors import InvalidCredentialsError, UsernameTakenError
from app.core.security import hash_password, verify_password
from app.models.user import User, UserLogin, UserRegister, UserSettings, UserSettingsUpdate
from app.repositories import user_repository


def to_user_model(document: dict) -> User:
    merged_settings = {**user_repository.DEFAULT_SETTINGS, **document.get("settings", {})}
    return User(
        id=str(document["_id"]),
        username=document["username"],
        settings=UserSettings(**merged_settings),
        created_at=document["created_at"],
    )


async def register(db: AsyncIOMotorDatabase, payload: UserRegister) -> User:
    document = {
        "username": payload.username,
        "password_hash": hash_password(payload.password),
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
    document = await user_repository.find_by_id(db, user_id)
    current_settings = {**user_repository.DEFAULT_SETTINGS, **document.get("settings", {})}

    updates = payload.model_dump(exclude_unset=True, mode="json")
    current_settings.update(updates)

    updated = await user_repository.update_settings(db, user_id, current_settings)
    return to_user_model(updated)
