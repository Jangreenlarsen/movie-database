from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user, require_admin
from app.db import get_database
from app.models.reservation import (
    AdminHoldCreate,
    Reservation,
    ReservationCreate,
    ScreeningReservationsCleared,
    SeatMap,
)
from app.services import audit_log_service, reservation_service

# Feature #133 — sæde-reservation til Voldby BIO. Routes spænder over to
# prefikser (fremvisnings-nested sædekort/reservation + de reservations-
# centrerede admin-actions), så routeren sætter ingen fælles prefix og
# angiver fulde stier. Alt kræver login; kun sædekort + reservér er åbne for
# guests (deres ene skrivehandling, jf. #62/#72), resten er admin-only.
router = APIRouter(tags=["reservations"])


@router.get("/api/screenings/{screening_id}/seats", response_model=SeatMap)
async def get_seat_map(
    screening_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await reservation_service.get_seat_map(db, screening_id, current_user["username"])


@router.post(
    "/api/screenings/{screening_id}/reservations",
    response_model=list[Reservation],
    status_code=201,
)
async def reserve_seats(
    screening_id: str,
    payload: ReservationCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    # Bevidst plain get_current_user (ikke require_not_guest): en guest må
    # reservere et sæde, præcis som de må ønske en visning (#62/#72) —
    # MEDMINDRE visningen er markeret privat (feature #170), tjekket inde i
    # selve reserve_seats (kræver screeningens data, ikke kun rollen).
    # Feature #227 — `reserved_for` gør kaldet til en admin-handling; rollen
    # tjekkes i service-laget, da den afhænger af payloadet.
    result = await reservation_service.reserve_seats(
        db,
        screening_id,
        payload.seat_ids,
        current_user["username"],
        current_user["role"],
        reserved_for=payload.reserved_for,
        admin=current_user,
    )
    if payload.reserved_for is not None and result:
        seats = ", ".join(str(r.seat_number) for r in result)
        await audit_log_service.record(
            db,
            current_user["username"],
            "reservation.added_for_user",
            f"Sæde {seats} — {result[0].reserved_by}",
        )
    return result


@router.delete(
    "/api/screenings/{screening_id}/reservations",
    response_model=ScreeningReservationsCleared,
    dependencies=[Depends(require_admin)],
)
async def clear_screening_reservations(
    screening_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    # Feature #227 — "Ryd alle tilmeldte" på én visning.
    result = await reservation_service.clear_screening_reservations(db, screening_id)
    await audit_log_service.record(
        db,
        current_user["username"],
        "reservation.cleared",
        f"{result.removed} reservation(er) på fremvisning {screening_id}",
    )
    return result


@router.get(
    "/api/reservations",
    response_model=list[Reservation],
    dependencies=[Depends(require_admin)],
)
async def list_reservations(
    status: str | None = Query(default=None),
    screening_id: str | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await reservation_service.list_reservations(db, status, screening_id)


# Registreret før /{reservation_id}-ruterne — samme konvention som
# screening_requests.py's /mine.
@router.get("/api/reservations/mine", response_model=list[Reservation])
async def list_my_reservations(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await reservation_service.list_my_reservations(db, current_user["username"])


@router.post(
    "/api/reservations/hold",
    response_model=Reservation,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_hold(
    payload: AdminHoldCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await reservation_service.create_hold(db, payload, current_user["username"])
    await audit_log_service.record(
        db,
        current_user["username"],
        "reservation.hold",
        f"Sæde {result.seat_number} ({result.scope})",
    )
    return result


@router.post(
    "/api/reservations/{reservation_id}/approve",
    response_model=Reservation,
    dependencies=[Depends(require_admin)],
)
async def approve_reservation(
    reservation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await reservation_service.approve_reservation(db, reservation_id, current_user)
    await audit_log_service.record(
        db,
        current_user["username"],
        "reservation.approved",
        f"Sæde {result.seat_number} — {result.reserved_by}",
    )
    return result


@router.delete("/api/reservations/{reservation_id}", status_code=204)
async def cancel_reservation(
    reservation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    # Ejeren kan slette sin egen reservation — også en godkendt, det er
    # "meld fra" i Mine pladser (feature #227) — en admin enhver. Håndhæves
    # i service-laget (CLAUDE.md regel 16).
    await reservation_service.cancel_reservation(db, reservation_id, current_user)
