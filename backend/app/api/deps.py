from fastapi import Cookie, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import (
    AccountDisabledError,
    AccountPendingError,
    AccountRejectedError,
    NotAuthenticatedError,
    NotAuthorizedError,
)
from app.core.security import decode_access_token
from app.db import get_database
from app.models.user import UserStatus
from app.repositories import user_repository

COOKIE_NAME = "access_token"


async def _resolve_user(
    access_token: str | None, db: AsyncIOMotorDatabase
) -> dict:
    if not access_token:
        raise NotAuthenticatedError()

    payload = decode_access_token(access_token)
    if not payload:
        raise NotAuthenticatedError()

    user = await user_repository.find_by_id(db, payload["sub"])
    if user is None:
        raise NotAuthenticatedError()

    return user


async def get_current_user_any_status(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """Identity only, no approval-status gate (feature #66) — used
    exclusively by `GET /api/users/me` so a still-pending or rejected user
    can at least see their own status instead of getting stuck behind a
    generic 403 with no way to tell what's wrong."""
    return await _resolve_user(access_token, db)


async def get_current_user(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    user = await _resolve_user(access_token, db)
    status = user.get("status", UserStatus.ACTIVE.value)
    if status == UserStatus.PENDING.value:
        raise AccountPendingError()
    if status == UserStatus.REJECTED.value:
        raise AccountRejectedError()
    if status == UserStatus.DISABLED.value:
        raise AccountDisabledError()
    return user


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise NotAuthorizedError()
    return current_user


async def require_not_guest(current_user: dict = Depends(get_current_user)) -> dict:
    """Feature #72 — blocks the read-only guest role from every write
    endpoint (create/update/delete movies/TV-shows/screening-requests).
    Enforced here so it can never be bypassed by calling the API directly,
    regardless of what the frontend does or doesn't render."""
    if current_user.get("role") == "guest":
        raise NotAuthorizedError("Gæster har kun læseadgang")
    return current_user
