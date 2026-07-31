from fastapi import APIRouter, Depends, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import COOKIE_NAME
from app.core.config import settings
from app.core.security import create_access_token
from app.db import get_database
from app.models.user import User, UserLogin, UserRegister
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookie(response: Response, user_id: str) -> None:
    token = create_access_token(user_id)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.post("/register", response_model=User, status_code=201)
async def register(
    payload: UserRegister,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await auth_service.register(db, payload)
    _set_auth_cookie(response, user.id)
    return user


@router.post("/login", response_model=User)
async def login(
    payload: UserLogin,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await auth_service.authenticate(db, payload)
    _set_auth_cookie(response, user.id)
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
