from fastapi import Cookie, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import NotAuthenticatedError
from app.core.security import decode_access_token
from app.db import get_database
from app.repositories import user_repository

COOKIE_NAME = "access_token"


async def get_current_user(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncIOMotorDatabase = Depends(get_database),
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
