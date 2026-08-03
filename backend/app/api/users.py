from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, get_current_user_any_status, require_admin
from app.db import get_database
from app.models.user import (
    PasswordChange,
    User,
    UserRoleUpdate,
    UserSettingsUpdate,
    UserStatusUpdate,
)
from app.services import audit_log_service, auth_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user_any_status)):
    # Deliberately the status-unaware dependency (feature #66) — a
    # still-pending or rejected user needs to see their own status here
    # instead of getting a generic 403 with no explanation.
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
    user_id: str,
    payload: UserRoleUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    updated = await auth_service.update_user_role(db, user_id, payload.role)
    await audit_log_service.record(
        db,
        current_user["username"],
        "user.role_changed",
        f"{updated.username}: rolle sat til {updated.role.value}",
    )
    return updated


@router.patch("/{user_id}/status", response_model=User, dependencies=[Depends(require_admin)])
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    updated = await auth_service.update_user_status(db, user_id, payload.status)
    await audit_log_service.record(
        db,
        current_user["username"],
        "user.approved" if payload.status == "active" else "user.rejected",
        updated.username,
    )
    return updated
