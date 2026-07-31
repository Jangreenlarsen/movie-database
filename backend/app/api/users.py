from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.user import PasswordChange, User, UserRoleUpdate, UserSettingsUpdate
from app.services import auth_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
    return auth_service.to_user_model(current_user)


@router.patch("/me/settings", response_model=User)
async def update_my_settings(
    payload: UserSettingsUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await auth_service.update_settings(db, str(current_user["_id"]), payload)


@router.post("/me/password", status_code=204)
async def change_my_password(
    payload: PasswordChange,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await auth_service.change_password(db, str(current_user["_id"]), payload)


@router.get("", response_model=list[User], dependencies=[Depends(require_admin)])
async def list_users(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await auth_service.list_users(db)


@router.patch("/{user_id}/role", response_model=User, dependencies=[Depends(require_admin)])
async def update_user_role(
    user_id: str, payload: UserRoleUpdate, db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await auth_service.update_user_role(db, user_id, payload.role)
