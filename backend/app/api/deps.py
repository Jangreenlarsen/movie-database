from fastapi import Cookie, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import (
    AccountDisabledError,
    AccountPendingError,
    AccountRejectedError,
    MustChangePasswordError,
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


def _check_status(user: dict) -> None:
    status = user.get("status", UserStatus.ACTIVE.value)
    if status == UserStatus.PENDING.value:
        raise AccountPendingError()
    if status == UserStatus.REJECTED.value:
        raise AccountRejectedError()
    if status == UserStatus.DISABLED.value:
        raise AccountDisabledError()


async def get_current_user_allow_password_change(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """Same status gate as `get_current_user`, but does NOT also block on
    `must_change_password` (feature #172) — used exclusively by
    `POST /users/me/password`, so a user forced to change their password
    after an admin reset (#171) has a way to actually do it. Without this
    escape hatch, `must_change_password` would be a permanent lockout no
    one — not even the affected user — could resolve (CLAUDE.md regel 16),
    the same reasoning as `get_current_user_any_status` below."""
    user = await _resolve_user(access_token, db)
    _check_status(user)
    return user


async def get_current_user(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    user = await _resolve_user(access_token, db)
    _check_status(user)
    if user.get("must_change_password", False):
        raise MustChangePasswordError()
    return user


async def get_optional_user(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict | None:
    """Feature #125 — for det offentlige besøgs-endpoint: den delbare /bio-side
    har ingen login, men et *indlogget* besøg skal stadig kunne kobles til
    brugernavnet. Returnerer brugeren hvis der er en gyldig cookie, ellers None
    — kaster aldrig 401 (i modsætning til `get_current_user`), så et anonymt
    besøg går lige så stille igennem som et indlogget."""
    if not access_token:
        return None
    payload = decode_access_token(access_token)
    if not payload:
        return None
    return await user_repository.find_by_id(db, payload["sub"])


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


def enforce_guest_wishlist_only(current_user: dict, payload) -> None:
    """Feature #116 — gæster må oprette ønsker, men intet i selve biblioteket,
    og aldrig sætte bestillingsstatus. Håndhæves i backend (CLAUDE.md regel 16),
    ikke kun som en UI-bekvemmelighed der er triviel at omgå. Bruges af
    `POST /api/movies` og `POST /api/tv-shows`, som derfor ikke længere kan
    bruge `require_not_guest`. Muterer payloaden: `order_status` nulstilles
    ubetinget for gæster, uanset hvad de sender."""
    if current_user.get("role") != "guest":
        return
    if not getattr(payload, "is_wishlist", False):
        raise NotAuthorizedError("Gæster kan kun oprette ønsker")
    payload.order_status = None
