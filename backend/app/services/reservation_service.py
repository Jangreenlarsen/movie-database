from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.errors import (
    InvalidSeatError,
    NotAuthorizedError,
    ReservationNotFoundError,
    ScreeningNotFoundError,
    SeatTakenError,
)
from app.models.reservation import (
    SEAT_IDS,
    SEAT_NUMBER_BY_ID,
    SEATS,
    AdminHoldCreate,
    Reservation,
    SeatMap,
    SeatMapEntry,
)
from app.repositories import reservation_repository, screening_repository
from app.services import screening_service


async def _to_model(db: AsyncIOMotorDatabase, document: dict) -> Reservation:
    """Beriger en reservation med sæde-nummer (fra det faste katalog) og —
    til konduktør-køen — hvilken film/fremvisning den gælder. Titlen slås op
    ved læsning frem for at blive kopieret ned på dokumentet, samme mønster
    som screening_service."""
    screening_title = None
    screening_at = None
    if document.get("screening_id"):
        screening = await screening_repository.find_by_id(db, document["screening_id"])
        if screening is not None:
            screening_at = screening.get("scheduled_at")
            display = await screening_service._resolve_display_info(
                db,
                screening["media_kind"],
                screening.get("movie_id"),
                screening.get("tv_show_id"),
            )
            screening_title = display.get("title")
    return Reservation(
        id=str(document["_id"]),
        seat_id=document["seat_id"],
        seat_number=SEAT_NUMBER_BY_ID.get(document["seat_id"], 0),
        scope=document["scope"],
        screening_id=document.get("screening_id"),
        status=document["status"],
        is_hold=document.get("is_hold", False),
        reserved_by=document["reserved_by"],
        created_at=document["created_at"],
        updated_at=document["updated_at"],
        approved_by=document.get("approved_by"),
        screening_title=screening_title,
        screening_at=screening_at,
    )


def _seat_status(entries: list[dict], username: str) -> tuple[str, str | None, bool | None]:
    """Én sædes tilstand set fra `username`s perspektiv, ud fra de
    reservationer der rammer sædet (dets egne + evt. globalt hold)."""
    if not entries:
        return "free", None, None
    # Egen reservation vinder — men aldrig et hold (hold er admin-blokke, ikke
    # personlige sæder man kan annullere fra sædekortet).
    mine = next(
        (r for r in entries if r["reserved_by"] == username and not r.get("is_hold")),
        None,
    )
    if mine is not None:
        return "mine", str(mine["_id"]), mine["status"] == "approved"
    # En andens: godkendt/hold → optaget; ellers stadig kun afventende.
    if any(r["status"] == "approved" or r.get("is_hold") for r in entries):
        return "taken", None, None
    return "pending", None, None


async def get_seat_map(db: AsyncIOMotorDatabase, screening_id: str, username: str) -> SeatMap:
    screening = await screening_repository.find_by_id(db, screening_id)
    if screening is None:
        raise ScreeningNotFoundError(screening_id)
    context = await reservation_repository.find_for_screening_context(db, screening_id)
    by_seat: dict[str, list[dict]] = {}
    for reservation in context:
        by_seat.setdefault(reservation["seat_id"], []).append(reservation)

    seats: list[SeatMapEntry] = []
    for seat in SEATS:
        status, reservation_id, approved = _seat_status(by_seat.get(seat["id"], []), username)
        seats.append(
            SeatMapEntry(
                seat_id=seat["id"],
                number=seat["number"],
                status=status,
                reservation_id=reservation_id,
                approved=approved,
            )
        )
    return SeatMap(screening_id=screening_id, seats=seats)


async def reserve_seats(
    db: AsyncIOMotorDatabase, screening_id: str, seat_ids: list[str], username: str
) -> list[Reservation]:
    screening = await screening_repository.find_by_id(db, screening_id)
    if screening is None:
        raise ScreeningNotFoundError(screening_id)

    invalid = [sid for sid in seat_ids if sid not in SEAT_IDS]
    if invalid:
        raise InvalidSeatError(invalid[0])

    # Bevar rækkefølge, fjern dubletter i selve forespørgslen.
    requested = list(dict.fromkeys(seat_ids))
    now = datetime.now(timezone.utc)

    def _is_own(reservation: dict | None) -> bool:
        return (
            reservation is not None
            and reservation["reserved_by"] == username
            and reservation.get("screening_id") == screening_id
            and not reservation.get("is_hold")
        )

    # Tjek ALLE sæder før nogen indsættes, så en delvis reservation aldrig
    # efterlades hvis ét af sæderne allerede er optaget (CLAUDE.md regel 16).
    for seat_id in requested:
        conflict = await reservation_repository.find_seat_conflict(db, seat_id, screening_id)
        if conflict is not None and not _is_own(conflict):
            raise SeatTakenError(SEAT_NUMBER_BY_ID.get(seat_id, 0))

    created: list[dict] = []
    for seat_id in requested:
        existing = await reservation_repository.find_seat_conflict(db, seat_id, screening_id)
        if _is_own(existing):
            # Allerede gæstens eget sæde for denne fremvisning — idempotent.
            created.append(existing)
            continue
        document = {
            "seat_id": seat_id,
            "scope": "screening",
            "screening_id": screening_id,
            "status": "pending",
            "is_hold": False,
            "reserved_by": username,
            "created_at": now,
            "updated_at": now,
            "approved_by": None,
        }
        try:
            inserted = await reservation_repository.insert(db, document)
        except DuplicateKeyError:
            # Et andet samtidigt kald nåede sædet mellem tjek og indsættelse —
            # det unikke index er backstoppet (BUGS.md #44-mønster).
            raise SeatTakenError(SEAT_NUMBER_BY_ID[seat_id])
        created.append(inserted)

    return [await _to_model(db, document) for document in created]


async def create_hold(
    db: AsyncIOMotorDatabase, payload: AdminHoldCreate, admin_username: str
) -> Reservation:
    if payload.seat_id not in SEAT_IDS:
        raise InvalidSeatError(payload.seat_id)
    now = datetime.now(timezone.utc)

    if payload.scope == "screening":
        screening = await screening_repository.find_by_id(db, payload.screening_id)
        if screening is None:
            raise ScreeningNotFoundError(payload.screening_id or "")
        conflict = await reservation_repository.find_seat_conflict(
            db, payload.seat_id, payload.screening_id
        )
    else:
        # Et globalt hold blokerer sædet overalt og konflikter derfor med
        # enhver eksisterende reservation på sædet.
        conflict = await reservation_repository.find_any_for_seat(db, payload.seat_id)

    if conflict is not None:
        raise SeatTakenError(SEAT_NUMBER_BY_ID.get(payload.seat_id, 0))

    document = {
        "seat_id": payload.seat_id,
        "scope": payload.scope,
        "screening_id": payload.screening_id if payload.scope == "screening" else None,
        "status": "approved",
        "is_hold": True,
        "reserved_by": admin_username,
        "created_at": now,
        "updated_at": now,
        "approved_by": admin_username,
    }
    try:
        inserted = await reservation_repository.insert(db, document)
    except DuplicateKeyError:
        raise SeatTakenError(SEAT_NUMBER_BY_ID.get(payload.seat_id, 0))
    return await _to_model(db, inserted)


async def approve_reservation(
    db: AsyncIOMotorDatabase, reservation_id: str, admin_username: str
) -> Reservation:
    existing = await reservation_repository.find_by_id(db, reservation_id)
    if existing is None:
        raise ReservationNotFoundError(reservation_id)
    updated = await reservation_repository.update(
        db,
        reservation_id,
        {
            "status": "approved",
            "approved_by": admin_username,
            "updated_at": datetime.now(timezone.utc),
        },
    )
    return await _to_model(db, updated)


async def cancel_reservation(
    db: AsyncIOMotorDatabase, reservation_id: str, current_user: dict
) -> None:
    existing = await reservation_repository.find_by_id(db, reservation_id)
    if existing is None:
        raise ReservationNotFoundError(reservation_id)
    is_admin = current_user.get("role") == "admin"
    if not is_admin and existing["reserved_by"] != current_user["username"]:
        raise NotAuthorizedError("Du kan kun annullere dine egne reservationer")
    await reservation_repository.delete(db, reservation_id)


async def list_reservations(
    db: AsyncIOMotorDatabase, status: str | None = None, screening_id: str | None = None
) -> list[Reservation]:
    documents = await reservation_repository.find_all(db, status, screening_id)
    return [await _to_model(db, document) for document in documents]


async def list_my_reservations(
    db: AsyncIOMotorDatabase, username: str
) -> list[Reservation]:
    documents = await reservation_repository.find_for_user(db, username)
    return [await _to_model(db, document) for document in documents]
