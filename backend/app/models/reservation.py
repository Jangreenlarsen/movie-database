from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Feature #133 — Voldby BIO har én fast sal: 14 sæder på tre niveauer,
# nummereret fortløbende 1–14 (som i sæde-vælger-artefakten). Selve layoutet
# (sofa-fløje, rækker) er ren præsentation og bor i frontend; backend kender
# kun sædernes id + nummer, så den kan validere input og beregne tilstande.
SEATS: list[dict] = [
    {"id": "N1-1", "number": 1, "row": "sofa"},
    {"id": "N1-2", "number": 2, "row": "sofa"},
    {"id": "N1-3", "number": 3, "row": "sofa"},
    {"id": "N1-4", "number": 4, "row": "sofa"},
    {"id": "N2-1", "number": 5, "row": "row2"},
    {"id": "N2-2", "number": 6, "row": "row2"},
    {"id": "N2-3", "number": 7, "row": "row2"},
    {"id": "N2-4", "number": 8, "row": "row2"},
    {"id": "N2-5", "number": 9, "row": "row2"},
    {"id": "N3-1", "number": 10, "row": "row3"},
    {"id": "N3-2", "number": 11, "row": "row3"},
    {"id": "N3-3", "number": 12, "row": "row3"},
    {"id": "N3-4", "number": 13, "row": "row3"},
    {"id": "N3-5", "number": 14, "row": "row3"},
]

SEAT_NUMBER_BY_ID: dict[str, int] = {s["id"]: s["number"] for s in SEATS}
SEAT_IDS: set[str] = set(SEAT_NUMBER_BY_ID)

ReservationScope = Literal["screening", "global"]
ReservationStatus = Literal["pending", "approved"]
# Beregnet pr. sæde fra den enkelte kalders perspektiv (aldrig gemt): hvad
# sædet ser ud som for DIG på en bestemt fremvisning.
SeatStatus = Literal["free", "mine", "pending", "taken"]


class ReservationCreate(BaseModel):
    """En gæst reserverer et eller flere ledige sæder på en fremvisning."""

    seat_ids: list[str] = Field(min_length=1)


class AdminHoldCreate(BaseModel):
    """Admin for-reserverer et bestemt sæde. `global` blokerer sædet på ALLE
    fremvisninger; `screening` kun den valgte (og kræver da `screening_id`)."""

    seat_id: str
    scope: ReservationScope = "global"
    screening_id: str | None = None

    @model_validator(mode="after")
    def check_screening_ref(self) -> "AdminHoldCreate":
        if self.scope == "screening" and not self.screening_id:
            raise ValueError("screening_id er påkrævet når scope er 'screening'")
        return self


class Reservation(BaseModel):
    id: str
    seat_id: str
    seat_number: int
    scope: ReservationScope
    screening_id: str | None = None
    status: ReservationStatus
    is_hold: bool = False
    reserved_by: str
    created_at: datetime
    updated_at: datetime
    approved_by: str | None = None
    # Beriget ved læsning (konduktør-køen viser hvilken film reservationen
    # gælder) — aldrig kopieret ned på reservations-dokumentet, samme mønster
    # som screening_service's berigelse.
    screening_title: str | None = None
    screening_at: datetime | None = None


class SeatMapEntry(BaseModel):
    seat_id: str
    number: int
    status: SeatStatus
    # Sat når status == "mine", så gæsten kan annullere sin egen reservation
    # direkte fra sædekortet.
    reservation_id: str | None = None
    # Sat når status == "mine": True = godkendt af en konduktør, False = afventer.
    approved: bool | None = None


class SeatMap(BaseModel):
    screening_id: str
    seats: list[SeatMapEntry]
