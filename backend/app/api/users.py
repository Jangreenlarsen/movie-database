from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, get_current_user_any_status, require_admin
from app.db import get_database
from app.models.user import (
    PasswordChange,
    PasswordResetResult,
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


_STATUS_AUDIT_ACTIONS = {
    "active": "user.approved",
    "rejected": "user.rejected",
    "disabled": "user.disabled",
}


@router.patch("/{user_id}/status", response_model=User, dependencies=[Depends(require_admin)])
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    updated = await auth_service.update_user_status(
        db, user_id, payload.status, str(current_user["_id"])
    )
    # "active" covers both approving a pending signup and re-enabling a
    # disabled account (feature #66/#80) — the audit log's action name is
    # the same either way, distinguishable from the target's prior status
    # if ever needed by cross-referencing the log's own history.
    await audit_log_service.record(
        db,
        current_user["username"],
        _STATUS_AUDIT_ACTIONS.get(payload.status, "user.status_changed"),
        updated.username,
    )
    return updated


@router.post(
    "/{user_id}/reset-password",
    response_model=PasswordResetResult,
    dependencies=[Depends(require_admin)],
)
async def reset_user_password(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Feature #171 — admin-assisteret password recovery (intet e-mail-
    system). Audit-loggen optegner kun AT en nulstilling skete og for hvem
    — aldrig selve adgangskoden (CLAUDE.md regel 6's princip anvendt på
    adgangskoder, ikke kun API-nøgler)."""
    username, new_password = await auth_service.admin_reset_password(db, user_id)
    await audit_log_service.record(db, current_user["username"], "user.password_reset", username)
    return PasswordResetResult(username=username, new_password=new_password)


@router.delete("/{user_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    deleted = await auth_service.delete_user(db, user_id, str(current_user["_id"]))
    await audit_log_service.record(db, current_user["username"], "user.deleted", deleted.username)
