from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.db import get_database
from app.models.user import User, UserSettingsUpdate
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
