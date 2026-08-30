from fastapi import APIRouter, Depends, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import COOKIE_NAME
from app.core.config import settings
from app.core.security import create_access_token
from app.db import get_database
from app.models.user import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    User,
    UserLogin,
    UserRegister,
)
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


# Feature #205 — bevidst UDEN `Depends(get_current_user)`: begge disse
# endpoints skal netop kunne bruges af en der IKKE er logget ind (det er jo
# hele pointen med "glemt adgangskode"). `forgot-password` svarer altid ens
# (se auth_service.request_password_reset's anti-enumererings-begrundelse).
@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    base_url = auth_service.resolve_reset_base_url(
        request.headers.get("origin"), str(request.base_url)
    )
    await auth_service.request_password_reset(db, payload.email, base_url)
    return ForgotPasswordResponse(
        message="Hvis denne e-mail er registreret, har vi sendt et link til at nulstille adgangskoden."
    )


@router.post("/reset-password", status_code=204)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await auth_service.reset_password_with_token(db, payload.token, payload.new_password)
